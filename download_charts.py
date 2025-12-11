from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import glob
from datetime import datetime, timedelta
import argparse

# ===== TARGET CHART URLs =====
download_urls = [
    "https://charts.spotify.com/charts/view/regional-global-daily/2025-12-05",
    "https://charts.spotify.com/charts/view/regional-global-daily/2025-12-06",
    "https://charts.spotify.com/charts/view/regional-global-daily/2025-12-07"
]

def generate_date_strings(start_date: str, end_date: str):
    try:
        # Convert start and end dates to datetime objects
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.strptime(end_date, "%Y-%m-%d")

        # Generate and store date strings in a list
        date_strings: list(str) = []
        current_date = start_date
        while current_date <= end_date:
            date_string = current_date.strftime("%Y-%m-%d")
            date_strings.append(date_string)
            current_date += timedelta(days=1)

        return date_strings

    except ValueError:
        print("Invalid date format. Please use YYYY-MM-DD.")
        exit(1)

def wait_for_downloads(download_dir, timeout=40):
    """
    Wait until no .part files remain and at least one CSV exists.
    Returns list of CSV files.
    """
    end_time = time.time() + timeout

    while time.time() < end_time:
        part_files = glob.glob(os.path.join(download_dir, "*.part"))
        csv_files = glob.glob(os.path.join(download_dir, "*.csv"))

        if not part_files and csv_files:
            return csv_files

        time.sleep(0.5)

    return glob.glob(os.path.join(download_dir, "*.csv"))

def setup_webdriver_for_download():
    """
    Create a Selenium webdriver instance configured for downloading files.
    """
 
    options = webdriver.FirefoxOptions()
    # Keep headless off by default so you can manually log in; you can enable headless if you don't need manual interaction.
    # options.headless = True  # uncomment if you want headless
    options.set_preference("browser.download.folderList", 2) # 0=desktop,1=downloads,2=custom
    options.set_preference("browser.download.dir", DOWNLOAD_DIR)
    options.set_preference("browser.download.useDownloadDir", True)
    options.set_preference(
        "browser.helperApps.neverAsk.saveToDisk",
        "text/csv,application/csv,text/comma-separated-values,application/octet-stream"
    ) 
    options.set_preference("browser.download.manager.showWhenStarting", False)
    options.set_preference("pdfjs.disabled", True)

    # ===== START FIREFOX =====
    driver = webdriver.Firefox(service=FirefoxService(), options=options)
    
    return driver

def user_manual_login(driver):
    """
    Prompt user to log in manually.
    """
    driver.get("https://charts.spotify.com/charts/overview/global")
    input("Log in manually in the browser, then press Enter here to continue...")



# ===== DOWNLOAD LOOP =====
def download_charts(driver, download_urls):
    for url in download_urls:
        print(f"\nOpening: {url}")
        driver.get(url)

        try:
            # Locate the CSV download button
            csv_button = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, '//button[@aria-labelledby="csv_download"]'))
            )

            # Track CSV files before download
            before = set(glob.glob(os.path.join(DOWNLOAD_DIR, "*.csv")))

            csv_button.click()
            print("Clicked CSV download button — waiting for file...")

            # Wait for new CSV to appear
            after = wait_for_downloads(DOWNLOAD_DIR)

            new_files = [f for f in after if f not in before]

            if new_files:
                print("Downloaded:", os.path.basename(new_files[0]))
            else:
                print("WARNING: No new CSV detected, but check the folder.")

        except Exception as e:
            print(f"Error downloading CSV from {url}: {e}")



if __name__ == "__main__":    
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--start_date",
        type=str,
        help="Start date (YYYY-MM-DD)",
        default="2017-01-01",
    )
    parser.add_argument(
        "-e",
        "--end_date",
        type=str,
        help="End date (YYYY-MM-DD)",
        default=datetime.today().strftime("%Y-%m-%d"),
    )
    
    args = parser.parse_args()
    
    date_strs = generate_date_strings(args.start_date, args.end_date)
    
    # ===== ASK USER FOR FOLDER NAME =====
    # make this into cli input
    folder_name = "global_charts"

    DOWNLOAD_DIR = os.path.join(os.getcwd(), "data", folder_name)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    print(f"CSV files will be saved in: {DOWNLOAD_DIR}")

    already_downloaded = set(os.listdir(DOWNLOAD_DIR))
    print(f"{len(already_downloaded)} files already exist in download directory.")
    
    driver = setup_webdriver_for_download()
    user_manual_login(driver)
    
    def charts_already_downloaded(date_str):
        file_name = f"regional-global-daily-{date_str}.csv"
        return file_name in already_downloaded
    
    download_urls = [
        f"https://charts.spotify.com/charts/view/regional-global-daily/{d}"
        for d in date_strs
        if not charts_already_downloaded(d)
    ]
    
    download_charts(driver, download_urls)
    
    driver.quit()
    print("\nAll downloads completed!")
    print(f"Saved inside: {DOWNLOAD_DIR}")
