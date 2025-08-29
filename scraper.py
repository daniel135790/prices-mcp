import gzip
import json
import logging
import os
import re
import time
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
import xml.etree.ElementTree as ET

import aiofiles
import aiohttp
from playwright.async_api import Page, async_playwright

from cache import CacheManager

# Configure logging
logger = logging.getLogger(__name__)

class Scraper:
    def __init__(self):
            # Initialize cache
            self.cache = CacheManager({'type':'memory', 'default_ttl':1000})

            # Cache TTL settings (in seconds)
            self.cache_ttl = {
                'supermarkets': 86400,      # 24 hours
                'branches': 86400,          # 24 hours  
                'products': 1800,           # 30 minutes
                'prices': 300,              # 5 minutes
            }

    async def get_branch_products(
            self,
        page: Page,
        supermarket: Dict[str, Any],
        branch: Dict[str, Any],
        sync_log_id: Any = None,
    ) -> Dict[str, Any]:
        """Main function to process branch products"""
        print("Starting file download process...")
        downloaded_files = await self.download_recent_files(page, supermarket, branch)
        print(f"Downloaded files count: {len(downloaded_files)}")

        # Process downloaded files
        total_products_updated = 0
        print("Processing downloaded files...")
        
        for file_info in downloaded_files:
            print(f"Processing file: {file_info['fileName']}")
            processed_products = await self.process_gzip_file_from_storage(
                supermarket.get('id'),
                branch.get('id'),
                file_info['fileName'],
                file_info['originalFileName'],
            )
            print(f"Stored products count: {len(processed_products)}")
            total_products_updated += len(processed_products)

        print(f"Total products updated: {total_products_updated}")
        print("=== Sync completed successfully ===")
        
        return processed_products


    async def perform_login(self, page: Page, username: str, password: str):
        """Perform login on the page"""
        # Look for common login form elements
        print("Looking for login form elements...")
        username_selector = 'input[name="username"], input[name="email"], input[type="text"]'
        password_selector = 'input[name="password"], input[type="password"]'
        submit_selector = 'button[type="submit"], input[type="submit"], button:has-text("Login"), button:has-text("Submit")'
        
        print("Waiting for username field...")
        await page.wait_for_selector(username_selector, timeout=20000)
        
        print("Typing username...")
        await page.fill(username_selector, username)
        
        print("Typing password...")
        await page.fill(password_selector, password)
        
        print("Submitting login form...")
        async with page.expect_navigation(wait_until="networkidle"):
            await page.click(submit_selector)
        
        print("Login navigation completed")


    async def download_file(self, file_url: str) -> bytes:
        """Download file using aiohttp"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to download file. Status: {response.status}")
                    
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded_size = 0
                    chunks = []
                    
                    async for chunk in response.content.iter_chunked(8192):
                        chunks.append(chunk)
                        downloaded_size += len(chunk)
                        
                        # Show progress if content-length is available
                        if total_size > 0:
                            progress = (downloaded_size / total_size * 100)
                            print(f"\rDownloading: {progress:.2f}%", end="")
                    
                    print("\nDownload completed successfully!")
                    return b''.join(chunks)
                    
        except Exception as error:
            raise Exception(f"Download failed: {str(error)}")


    async def shufersal_scrape_and_download(
            self,
        page: Page,
        branch_id: int = 3,
        target_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Shufersal-specific scraping and download logic"""
        try:
            # Wait for the dropdown to be available
            print("Waiting for dropdown to load...")
            await page.wait_for_selector("#ddlStore", timeout=10000)
            
            # Click on the dropdown
            print("Clicking dropdown...")
            await page.click("#ddlStore")
            
            # Select option with value
            print(f"Selecting option with value={branch_id}...")
            await page.select_option("#ddlStore", value=str(branch_id))
            
            # Wait for the page to update after selection
            await asyncio.sleep(2)

            text_to_find = target_text or await self.get_most_updated_file_name(page)

            # Look for the specific td with the target text
            print(f"Looking for target cell with text: {text_to_find}")
            
            # Wait for the table to load and find the target cell
            await page.wait_for_function(
                f"""
                (text) => {{
                    const tds = document.querySelectorAll("td");
                    return Array.from(tds).some(td => td.textContent.includes(text));
                }}
                """,
                arg=text_to_find,
                timeout=10000
            )
            
            # Find the td with the target text and get the download link
            download_url = await page.evaluate(
                f"""
                (textToFind) => {{
                    const tds = document.querySelectorAll("td");
                    for (let td of tds) {{
                        if (td.textContent.includes(textToFind)) {{
                            // Found the target td, now go to the first td in the same row
                            const row = td.closest("tr");
                            if (row) {{
                                const firstTd = row.querySelector("td:first-child");
                                if (firstTd) {{
                                    const link = firstTd.querySelector("a");
                                    if (link && link.href) {{
                                        return link.href.replace("\\n", "");
                                    }}
                                }}
                            }}
                        }}
                    }}
                    return null;
                }}
                """,
                text_to_find
            )
            
            if download_url:
                download_url = download_url.replace("\n", "").replace("\\n", "")
            
            if not download_url:
                raise Exception(f"Could not find download link for: {text_to_find}")
            
            print(f"Found download URL for {text_to_find}: {download_url}")
            
            # Download the file
            print("Downloading file...")
            buffer = await self.download_file(download_url)
            print(f"Downloaded file for {text_to_find}, size: {len(buffer)} bytes")

            file_name = f"{int(time.time() * 1000)}_{text_to_find}.gz"
            full_file_name = await self.save_file(file_name, buffer)

            return {
                'fileName': full_file_name,
                'originalFileName': text_to_find,
                'buffer': buffer
            }
            
        except Exception as error:
            print(f"Error during Shufersal scraping: {error}")
            raise error


    async def get_most_updated_file_name(self, page: Page) -> str:
        """Get the most recently updated file name from the page"""

        fileNamesToUpdateTime = await page.evaluate(
            """
            () => {
                const trs = Array.from(document.querySelectorAll("tbody tr"));
                const fileNamesToUpdateTime = trs.map(tr => {
                    const tds = tr.querySelectorAll("td");
                    return { 
                        updateTime: tds[1].textContent, 
                        fileName: tds[6].textContent 
                    };
                });

                return fileNamesToUpdateTime;
            }
            """
        )

        fileNamesToUpdateTime = list(map(lambda item: {
            'updateTime': item['updateTime'],
            'fileName': item['fileName']
        }, fileNamesToUpdateTime))

        print("File names with update times:", [i['fileName'] for i in fileNamesToUpdateTime])
        fileNamesToUpdateTime.sort(key=lambda x: x['updateTime'])

        print("Sorted file names by update time:", [i['fileName'] for i in fileNamesToUpdateTime])

        item = next((item for item in fileNamesToUpdateTime if "PriceFull" in item['fileName']), None)
        print("Found item", item)

        return item['fileName'] if item else None


    async def download_recent_files(
            self,
        page: Page, 
        supermarket: Dict[str, Any], 
        branch: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Download recent files from the page"""
        files = []

        # If test file names are specified, download only those files
        test_file_names = supermarket.get('test_file_names', [])
        if test_file_names:
            print(f"Testing mode: downloading specific files: {', '.join(test_file_names)}")
            
            # Try Shufersal-specific scraping logic first for test files
            try:
                for file_name in test_file_names:
                    try:
                        print(f"Looking for test file: {file_name}")
                        file_info = await shufersal_scrape_and_download(
                            page,
                            branch.get('branch_id'),
                            file_name,
                        )
                        files.append(file_info)
                    except Exception as error:
                        print(f"Failed to download test file {file_name} using Shufersal logic: {error}")
            except Exception as error:
                print(f"Error during Shufersal test file scraping: {error}")
            
            # If no files were downloaded with Shufersal logic, fallback to original test file logic
            if not files:
                print("Falling back to generic test file logic...")
                for file_name in test_file_names:
                    try:
                        print(f"Looking for test file: {file_name}")
                        
                        # Look for links containing the specific file name
                        try:
                            file_link = await page.get_attribute(
                                f'a[href*="{file_name}"], a[title*="{file_name}"]',
                                'href'
                            )
                        except:
                            file_link = None
                        
                        if file_link:
                            print(f"Downloading test file: {file_name}")
                            buffer = await download_file(file_link)
                            print(f"Downloaded test file {file_name}, size: {len(buffer)} bytes")
                            
                            storage_file_name = f"{int(time.time() * 1000)}_{file_name}"
                            await save_file(storage_file_name, buffer)
                            
                            files.append({
                                'fileName': storage_file_name,
                                'originalFileName': file_name,
                                'buffer': buffer,
                            })
                        else:
                            print(f"Test file not found: {file_name}")
                            
                    except Exception as error:
                        print(f"Failed to download test file {file_name}: {error}")
            
            return files

        try:
            file_info = await self.shufersal_scrape_and_download(page, branch.get('branch_id'))
            files.append(file_info)
            print("File downloaded successfully!")
        except Exception as error:
            print(f"Error during Shufersal scraping: {error}")
            # Fallback to original generic logic if Shufersal-specific scraping fails
            print("Falling back to generic download logic...")
            
            # Look for file download links
            print("Looking for download links...")
            try:
                download_links = await page.evaluate(
                    """
                    () => {
                        const links = Array.from(document.querySelectorAll('a[href*=".gz"], a[href*="download"]'));
                        return links.map(link => ({
                            href: link.href,
                            text: link.textContent,
                            title: link.title,
                            fileName: link.href.split("/").pop() || "",
                        }));
                    }
                    """
                )
                
                print(f"Found {len(download_links)} potential download links")
                
                # Filter by file name pattern if specified
                filtered_links = download_links
                file_name_pattern = supermarket.get('file_name_pattern')
                if file_name_pattern:
                    pattern = re.compile(file_name_pattern, re.IGNORECASE)
                    filtered_links = [
                        link for link in download_links
                        if pattern.search(link['fileName']) or 
                        pattern.search(link['text']) or 
                        pattern.search(link['title'])
                    ]
                    print(f"Filtered {len(download_links)} links to {len(filtered_links)} using pattern: {file_name_pattern}")
                
                for link in filtered_links:
                    print("Checking link:", link['href'])
                    # Check if file is recent (this would need to be customized per supermarket)
                    # For now, download all .gz files
                    if '.gz' in link['href']:
                        try:
                            file_name = link['fileName'] or link['href']
                            print(f"Downloading file: {file_name}")
                            buffer = await download_file(link['href'])
                            print(f"Downloaded file {file_name}, size: {len(buffer)} bytes")
                            
                            storage_file_name = f"{int(time.time() * 1000)}_{link['fileName'] or 'download'}"
                            await save_file(storage_file_name, buffer)
                            
                            files.append({
                                'fileName': storage_file_name,
                                'originalFileName': link['fileName'] or 'download',
                                'buffer': buffer,
                            })
                            
                            # Limit to prevent downloading too many files in production
                            if len(files) >= 10:
                                print("Reached file download limit (10 files)")
                                break
                                
                        except Exception as error:
                            print(f"Failed to download file {link['fileName'] or link['href']}: {error}")
                            
            except Exception as error:
                print(f"Error finding download links: {error}")

        print(f"Total files downloaded: {len(files)}")
        return files


    async def process_gzip_file_from_storage(
            self,
        supermarket_id: int,
        branch_record_id: int,
        gz_file_name: str,
        original_file_name: str,
    ) -> int:
        """Process gzip file from local storage"""
        try:
            print(f"Processing gz file from storage: {gz_file_name}")

            # Read gz file from local storage
            async with aiofiles.open(gz_file_name, 'rb') as f:
                gz_data = await f.read()

            print(f"Read gz file from storage, size: {len(gz_data)}")

            # Decompress gz file
            xml_buffer = self.decompress_gzip(gz_data)
            print(f"Decompressed XML size: {len(xml_buffer)}")

            # Save XML to local storage for chunked processing
            xml_file_name = f"{int(time.time() * 1000)}_{original_file_name}.xml"
            
            async with aiofiles.open(xml_file_name, 'wb') as f:
                await f.write(xml_buffer)

            print(f"Saved XML file to storage: {xml_file_name}")

            # Process XML in chunks
            processed_products = await self.process_xml_in_chunks(
                supermarket_id,
                branch_record_id,
                xml_file_name,
            )

            # Clean up XML file after processing
            os.remove(xml_file_name)
            print(f"Cleaned up XML file: {xml_file_name}")

            return processed_products

        except Exception as error:
            print(f"Error processing gz file from storage: {error}")
            raise error


    async def process_xml_in_chunks(
            self,
        supermarket_id: int,
        branch_record_id: int,
        xml_file_name: str,
    ) -> int:
        """Process XML file in chunks"""
        try:
            print(f"Processing XML file in chunks: {xml_file_name}")
            all_products = []

            # Read XML file from storage
            async with aiofiles.open(xml_file_name, 'r', encoding='utf-8') as f:
                xml_content = await f.read()

            print(f"XML content length: {len(xml_content)}")

            # Parse the XML header and root data first
            header_patterns = {
                'chain_id': r'<ChainId>(.*?)</ChainId>',
                'sub_chain_id': r'<SubChainId>(.*?)</SubChainId>',
                'store_id': r'<StoreId>(.*?)</StoreId>',
                'bikoret_no': r'<BikoretNo>(.*?)</BikoretNo>',
            }

            root_data = {}
            for key, pattern in header_patterns.items():
                match = re.search(pattern, xml_content)
                root_data[key] = match.group(1) if match else ""

            print(f"Root data extracted: {root_data}")

            # Find the Items section and process products in chunks
            items_match = re.search(r'<Items[^>]*>(.*?)</Items>', xml_content, re.DOTALL)
            if not items_match:
                print("No Items section found in XML")
                return 0

            items_content = items_match.group(1)
            CHUNK_SIZE = 50  # Process 50 items at a time
            total_processed = 0

            # Split items using regex to find individual Item elements
            item_pattern = re.compile(r'<Item[^>]*>(.*?)</Item>', re.DOTALL)
            items = item_pattern.findall(items_content)

            print(f"Found {len(items)} items to process")

            # Process items in chunks
            for i in range(0, len(items), CHUNK_SIZE):
                chunk = items[i:i + CHUNK_SIZE]
                chunk_num = i // CHUNK_SIZE + 1

                if chunk_num % 10 == 0:
                    print(f"Processing chunk {chunk_num}/{(len(items) + CHUNK_SIZE - 1) // CHUNK_SIZE}")

                products = []

                for item_xml in chunk:
                    try:
                        product = self.parse_product_from_item_xml(item_xml, root_data)
                        if product:
                            products.append(product)
                            all_products.append(product)
                    except Exception as error:
                        print(f"Error parsing item: {error}")

                # Store this chunk of products
                stored = await self.store_products_in_batch(
                    supermarket_id,
                    branch_record_id,
                    products,
                )

                total_processed += stored
                print(f"Processed chunk: {stored} products stored")

                # Small delay to prevent overwhelming the system
                await asyncio.sleep(0.1)

            print(f"Total products processed: {total_processed}")
            return all_products

        except Exception as error:
             print(f"Error processing XML in chunks: {error}")
             raise error


    def parse_product_from_item_xml(self, item_xml: str, root_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse product data from item XML"""
        try:
            def extract_value(tag: str) -> str:
                pattern = f'<{tag}[^>]*>(.*?)</{tag}>'
                match = re.search(pattern, item_xml, re.DOTALL)
                return match.group(1).strip() if match else ""

            item_code = extract_value("ItemCode")
            item_name = extract_value("ItemName")
            price_str = extract_value("ItemPrice")

            if not item_code or not item_name or not price_str:
                return None

            try:
                price = float(price_str)
            except ValueError:
                return None

            date_str = extract_value("PriceUpdateDate")
            price_update_date = datetime.now().isoformat()
            if date_str:
                try:
                    parsed_date = datetime.fromisoformat(date_str.replace(" ", "T") + ":00")
                    price_update_date = parsed_date.isoformat()
                except ValueError:
                    print(f"Failed to parse date: {date_str}")

            quantity_str = extract_value("Quantity")
            quantity = float(quantity_str) if quantity_str else 0

            unit_of_measure_price_str = extract_value("UnitOfMeasurePrice")
            unit_of_measure_price = float(unit_of_measure_price_str) if unit_of_measure_price_str else None

            qty_in_package_str = extract_value("QtyInPackage")
            qty_in_package = int(qty_in_package_str) if qty_in_package_str else 0

            item_status_str = extract_value("ItemStatus")
            item_status = int(item_status_str) if item_status_str else 1

            return {
                **root_data,
                'price_update_date': price_update_date,
                'item_code': item_code,
                'item_type': extract_value("ItemType"),
                'item_name': item_name,
                'manufacturer_name': extract_value("ManufacturerName") or None,
                'manufacture_country': extract_value("ManufactureCountry") or None,
                'manufacturer_item_description': extract_value("ManufacturerItemDescription") or None,
                'unit_qty': extract_value("UnitQty"),
                'quantity': quantity,
                'b_is_weighted': extract_value("bIsWeighted") == "1",
                'unit_of_measure': extract_value("UnitOfMeasure"),
                'qty_in_package': qty_in_package,
                'item_price': price,
                'unit_of_measure_price': unit_of_measure_price,
                'allow_discount': extract_value("AllowDiscount") == "1",
                'item_status': item_status,
            }

        except Exception as error:
            print(f"Error parsing product from item XML: {error}")
            return None


    async def store_products_in_batch(
            self,
        supermarket_id: int,
        branch_record_id: int,
        products: List[Dict[str, Any]],
    ) -> int:
        """Store products in batch - replace with your preferred storage method"""
        if not products:
            return 0

        try:
            products_to_store = []
            for product_data in products:
                product_to_store = {
                    'supermarket_id': supermarket_id,
                    **product_data,
                    'updated_at': datetime.now().isoformat(),
                }
                products_to_store.append(product_to_store)

            # TODO: Replace this with your preferred storage method
            # For now, just save to JSON file as example
            output_file = f"files/products_{int(time.time() * 1000)}.json"
            async with aiofiles.open(output_file, 'w') as f:
                await f.write(json.dumps(products_to_store, indent=2, ensure_ascii=False))

            print(f"Successfully stored {len(products)} products to {output_file}")
            return len(products)

        except Exception as error:
            print(f"Error storing products in batch: {error}")
            return 0


    def decompress_gzip(self, gzip_data: bytes) -> bytes:
        """Decompress gzip data"""
        return gzip.decompress(gzip_data)


    async def save_file(self, file_name: str, file_data: bytes):
        """Save file to local storage"""
        try:
            os.makedirs("files", exist_ok=True)
            full_file_name = f"files/{file_name}"
            async with aiofiles.open(full_file_name, 'wb') as f:
                await f.write(file_data)
            print(f"Saved file: {file_name}")
            return full_file_name
        except Exception as error:
            print(f"Error saving file {file_name}: {error}")
            raise error


    # Example usage
    async def scrape(self):
        """Example usage of the scraping functions"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            # Example supermarket and branch data
            supermarket = {
                'id': 1,
                'test_file_names': [],  # Add test file names if needed
                'file_name_pattern': r'.*\.gz$'  # Pattern for file filtering
            }
            
            branch = {
                'id': 1,
                'branch_id': 3
            }
            
            try:
                # Navigate to the target site
                await page.goto("https://prices.shufersal.co.il")
                
                # Perform login if needed
                # await perform_login(page, "username", "password")
                
                # Process branch products
                result = await self.get_branch_products(page, supermarket, branch)
                print(f"Processing result: {len(result)}")
                
            except Exception as e:
                print(f"Error in main: {e}")
            finally:
                await browser.close()


def main():
    scraper = Scraper()
    asyncio.run(scraper.scrape())

if __name__ == "__main__":
    main()