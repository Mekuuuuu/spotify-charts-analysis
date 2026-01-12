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
from urllib.parse import quote
from dotenv import load_dotenv
import pandas as pd
from itertools import product
import winsound

def create_data_path(filename):
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data", filename)
    )

def generate_date_strings(start_date: str, end_date: str):
    try:
        # Convert start and end dates to datetime objects
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.strptime(end_date, "%Y-%m-%d")

        # Generate and store date strings in a list
        date_strings: list(str) = [] # type: ignore
        current_date = start_date
        while current_date <= end_date:
            date_string = current_date.strftime("%Y-%m-%d")
            date_strings.append(date_string)
            current_date += timedelta(days=1)

        return date_strings

    except ValueError:
        print("Invalid date format. Please use YYYY-MM-DD.")
        exit(1)

def read_lines_from_file(path: str):
    with open(path, "r") as f:
        lines = (
            f.read().splitlines()
        )
    return lines

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
    profile_path = os.path.abspath(os.path.join(os.getcwd(), "firefox_profile"))
    os.makedirs(profile_path, exist_ok=True)
    
    options = webdriver.FirefoxOptions()
    # Keep headless off by default so you can manually log in; you can enable headless if you don't need manual interaction.
    # options.headless = True  # uncomment if you want headless
    options.set_preference("browser.download.folderList", 2) # 0=desktop,1=downloads,2=custom
    options.set_preference("browser.download.dir", download_dir)
    options.set_preference("browser.download.useDownloadDir", True)
    options.set_preference(
        "browser.helperApps.neverAsk.saveToDisk",
        "text/csv,application/csv,text/comma-separated-values,application/octet-stream"
    ) 
    options.set_preference("browser.download.manager.showWhenStarting", False)
    options.set_preference("pdfjs.disabled", True)
    
    options.set_preference("permissions.default.image", 2)
    options.set_preference("permissions.default.stylesheet", 2)

    options.add_argument(f"-profile")
    options.add_argument(profile_path)
    
    # ===== START FIREFOX =====
    driver = webdriver.Firefox(service=FirefoxService(), options=options)
    
    return driver

def get_spotify_credentials():
    """
    Retrieve Spotify login credentials from environment variables.
    """
    # env_path = os.path.join(os.path.dirname(__file__), '..', ".env")
    # load_dotenv(env_path)
    # username = os.environ.get("SPOTIFY_USERNAME")
    # password = os.environ.get("SPOTIFY_PASSWORD")

    # if username is None or password is None:
    #     questions = []

    #     if username is None:
    #         questions.append(
    #             inquirer.Text("username", message="Enter your Spotify username:")
    #         )

    #     if password is None:
    #         questions.append(
    #             inquirer.Password("password", message="Enter your Spotify password:")
    #         )

    #     answers = inquirer.prompt(questions)
    #     if username is None:
    #         username = answers["username"]
    #     if password is None:
    #         password = answers["password"]

    return username, password

def fill_and_submit_login_form(driver: webdriver, username: str, password: str):
    """
    Provide credentials to login Spotify account.
    """
    login_page_url = "https://accounts.spotify.com/en/login"
    after_login_url="https://charts.spotify.com/charts/overview/global"
    
    driver.get(login_page_url + f"?continue={quote(after_login_url)}")
    
    wait = WebDriverWait(driver, 15)
    
    time.sleep(5) # REDIRECT DELAY
    
    username_input = wait.until(
        EC.presence_of_element_located((By.ID, "username"))
    )
    username_input.clear()
    username_input.send_keys(username)

    continue_btn = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, '[data-testid="login-button"]')
            )
        )
    
    while "accounts.spotify.com" in driver.current_url:
        continue_btn.click()
        time.sleep(5)

    time.sleep(5) # REDIRECT DELAY
    
    login_with_password_btn = wait.until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, '[data-encore-id="buttonTertiary"]')
        )
    )
    
    while "challenge.spotify.com" in driver.current_url:
        login_with_password_btn.click()
        time.sleep(5)
        
    time.sleep(5) # REDIRECT DELAY
    
    password_input = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="login-password"]'))
    )
    password_input.clear()
    password_input.send_keys(password)
    
    login_btn = wait.until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, '[data-testid="login-button"]')
        )
    )
    while "accounts.spotify.com" in driver.current_url:
        login_btn.click()
        time.sleep(5)

def go_to_spotify_charts(driver):
    """
    Navigate to Spotify Charts homepage.
    """
    charts_url = "https://charts.spotify.com"
    driver.get(charts_url)

def is_logged_in(driver):
    """
    Check if the user is logged in by looking at url 
    If redirected to charts.spotify.com/home, then not logged in.
    If redirected to charts.spotify.com/charts/overview/global, then logged in.
    """
    
    WebDriverWait(driver, 15).until(
        lambda d: "charts.spotify.com" in d.current_url
    )
    
    url = driver.current_url.lower()
    
    # Logged in users get redirected to /charts/...
    # Logged out users get /home
    if "/charts/" in url:
        return True

    if "/home" in url:
        return False

    # Fallback (Spotify sometimes shows intermediate pages)
    return False
        
def manual_login(driver):
    """
    Prompt user to log in manually.
    """
    login_page_url = "https://accounts.spotify.com/en/login"
    driver.get(login_page_url)
    
    input("Log in manually in the browser, then press Enter here to continue...")

def abort_program(driver, message):
    print(message)
    driver.quit()
    raise SystemExit(1)

DOWNLOAD_STATS = {
    "start_time": None,
    "end_time": None,
    "per_chart": [],
}

def _now():
    return time.time()

def _fmt(seconds):
    return f"{seconds:.2f}s"

def log_start():
    DOWNLOAD_STATS["start_time"] = _now()
    print("\n📥 Download session started")

def log_end():
    DOWNLOAD_STATS["end_time"] = _now()
    total = DOWNLOAD_STATS["end_time"] - DOWNLOAD_STATS["start_time"]

    per = DOWNLOAD_STATS["per_chart"]

    if per:
        avg = sum(per) / len(per)
        longest = max(per)
    else:
        avg = longest = 0

    print("\n📊 DOWNLOAD STATS")
    print(f"Total charts: {len(per)}")
    print(f"Total time: {_fmt(total)}")
    print(f"Average chart: {_fmt(avg)}")
    print(f"Slowest chart: {_fmt(longest)}")

def download_charts(driver, download_urls):
    log_start()
    
    for url in download_urls:
        print(f"\nOpening: {url}")
        
        chart_start = _now()
        
        backoff_time = 10
        downloaded = False

        driver.get(url)
        
        # Track CSV files before download
        before = set(glob.glob(os.path.join(download_dir, "*.csv")))
        
        while not downloaded:  
            try:
                # Locate the CSV download button
                csv_button = WebDriverWait(driver, backoff_time).until(
                    EC.element_to_be_clickable((By.XPATH, '//button[@aria-labelledby="csv_download"]'))
                )
            
                csv_button.click()
                print("Clicked CSV download button — waiting for file...")

                # Wait for new CSV to appear
                after = wait_for_downloads(download_dir)
                new_files = [f for f in after if f not in before]

                if new_files:
                    print("Downloaded:", os.path.basename(new_files[0]))
                    downloaded = True
                else:
                    print("WARNING: No new CSV detected, but check the folder.")

                backoff_time = 10  # reset backoff time after a successful download

            except Exception as e:
                if not is_logged_in(driver):
                    abort_program(driver, f"\n🚨 SPOTIFY SESSION LOST\n\nSpotify logged you out during the last download.\nLast attempted chart: {url}")
                
                # print(f"Error downloading CSV from {url}: {e}")
                print(f"Spotify throttling or stalling: {e}")
                print(f"Retrying download for {url}...")
                print(f"Backing off {backoff_time:.0f}s...")
                
                time.sleep(backoff_time)
                backoff_time = min(backoff_time * 1.7, 120)  # max 2 min
                
                driver.refresh()
            
        chart_end = _now()
        elapsed = chart_end - chart_start
        DOWNLOAD_STATS["per_chart"].append(elapsed)
    
    log_end()

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
    parser.add_argument(
        "-r",
        "--region_codes",
        type=str,
        help="List of regions to download charts for (two-letter country codes for countries, 'global' for global charts) - can be a path to a text file or a comma-separated list of codes",
        default=create_data_path(
            "region_names_and_codes.csv"
        ),  # path to file containing region names and codes for all regions with chart data on the Spotify Charts website; the 'code' column will be used for obtaining the region codes
        nargs="+",
    )
    parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        help="Path to directory where charts will be downloaded to",
        default=create_data_path("global_charts"),
    )
    args = parser.parse_args()
    
    date_strs = generate_date_strings(args.start_date, args.end_date)
    print(f"Fetching data for date range [{args.start_date}, {args.end_date}]")
    print(f"processing {len(date_strs)} dates")
    
    all_regions_and_codes_csv_path = create_data_path("region_names_and_codes.csv")
    
    if args.region_codes == all_regions_and_codes_csv_path:
        print(
            f"No region codes provided. Using region codes for all countries with Spotify Chart data from '{all_regions_and_codes_csv_path}'"
        )
        region_codes = pd.read_csv(all_regions_and_codes_csv_path)["code"].tolist()
    elif os.path.isfile(args.region_codes[0]):
        region_codes = read_lines_from_file(args.region_codes[0]) # useful to avoid multiple command line args if many region codes
    else:
        region_codes = args.region_codes
    
    region_codes = [r.strip().lower() for r in region_codes if r.strip()] # clean up region codes (no empty strings, no whitespace, no accidental '\n' or ' ')
    
    region_codes = [
        "global" if r == "ww" else r for r in region_codes
    ]  # replace region code 'ww' with 'global' for global charts (ww = worldwide; used in file under all_regions_and_codes_csv_path)
    print(f"processing {len(region_codes)} regions")
    regions_and_dates = list(product(region_codes, date_strs))
    print(
        f"processing {len(regions_and_dates)} charts (combinations of regions and dates)"
    )

    download_dir = os.path.join(os.getcwd(), "data", args.output_dir)
    os.makedirs(download_dir, exist_ok=True)

    print(f"CSV files will be saved in: {download_dir}")

    already_downloaded = set(os.listdir(download_dir))
    print(f"{len(already_downloaded)} files already exist in download directory.")
    
    def charts_already_downloaded(region_code, date_str):
        file_name = f"regional-{region_code}-daily-{date_str}.csv"
        return file_name in already_downloaded
    
    download_urls = [
        f"https://charts.spotify.com/charts/view/regional-{r}-daily/{d}"
        for (r, d) in regions_and_dates
        if not charts_already_downloaded(r, d)
    ]
    
    if len(download_urls) == 0:
        print("All charts already downloaded. Exiting.")
        exit(0)
    
    driver = setup_webdriver_for_download()
    
    go_to_spotify_charts(driver)
    if not is_logged_in(driver):
        print("Not logged in. Opening Spotify login...")
        manual_login(driver)
        
        go_to_spotify_charts(driver)
        if not is_logged_in(driver):
            print("Login failed. Exiting.")
            driver.quit()
            exit(1)
    
    print("Login successful!")
    
    download_charts(driver, download_urls)
    
    driver.quit()
    print("\nAll downloads completed!")
    print(f"Saved inside: {download_dir}")