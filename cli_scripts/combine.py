import os
import pandas as pd
import argparse
import re


def process_spotify_daily_charts_csv(file_path):
    try:
        df = pd.read_csv(file_path)
        # name of each daily charts file downloaded from https://charts.spotify.com is in format 'regional-<region_code>-daily-<YYYY-MM-DD>.csv'
        # region_code is two letter country code (e.g. 'us' for United States) except for global charts
        # global charts use region code 'global' -> replace with two letter code ('ww' for worldwide; not 'gl' as that is the official ISO code for Greenland)
        filename_components = os.path.basename(file_path).split(".csv")[0].split("-")

        region_code = filename_components[1]
        if region_code == "global":
            region_code = "ww"
        df.insert(0, "region_code", region_code)

        date_str = "-".join(filename_components[3:6])
        df.insert(0, "date", pd.to_datetime(date_str))
        df.date = df.date.dt.floor(
            "d"
        )  # set time component to 0 (midnight); should result in performant date queries https://stackoverflow.com/a/41718815/13727176

        def extract_track_id(uri):
            return uri.split(":")[-1]

        # replace uri column with track_id column
        df.insert(2, "track_id", df.uri.apply(extract_track_id))
        df = df.drop(columns=["uri"])

        df = df.rename(
            columns={"rank": "pos"}
        )  # rank has special meaning in pandas DF API, rename for convenience

        return df
    except Exception as e:
        print(f"Error reading file: {file_path}")
        print(e)
        return None
    
def combine_csv_files(
    directory,
    start_date: pd.Timestamp = None,
    end_date: pd.Timestamp = None,
    drop_redundant_columns: bool = False,
):
    
    filenames = [file for file in os.listdir(directory) if file.endswith(".csv")]

    # ignore duplicate files like (1).csv
    duplicate_pattern = r"\(\d+\)\.csv$"
    filenames = [f for f in filenames if not re.search(duplicate_pattern, f)]
    
    print(f"Found {len(filenames)} CSV files")

    all_dfs = []

    for fname in filenames:
        path = os.path.join(directory, fname)
        df = process_spotify_daily_charts_csv(path)
        if df is not None:
            all_dfs.append(df)
    
    if not all_dfs:
        raise RuntimeError("No valid CSV files were processed")

    print(f"Done processing files, combining results...")
    
    combined_df = pd.concat(all_dfs, ignore_index=True)

    # convert region codes to uppercase to match ISO 3166-1 alpha-2 country codes more closely and make joins with Spotify API data easier
    combined_df["region_code"] = combined_df["region_code"].str.upper()

    # sort by date, region_code, and pos
    combined_df = combined_df.sort_values(["date", "region_code", "pos"])

    if start_date is not None:
        combined_df = combined_df[combined_df["date"] >= start_date]

    if end_date is not None:
        combined_df = combined_df[combined_df["date"] <= end_date]
        
    # change data types to reduce memory usage
    # TODO: doesn't work for some reason (output file size not changing at all?!)
    combined_df["pos"] = pd.to_numeric(combined_df["pos"], downcast="unsigned")
    combined_df["streams"] = combined_df["streams"].astype("uint64")
    combined_df["region_code"] = combined_df["region_code"].astype("category")

    if drop_redundant_columns:
        columns_to_drop = [
            "artist_names",
            "track_name",
            "source",
            "peak_rank",
            "previous_rank",
            "days_on_chart",
        ]
        combined_df = combined_df.drop(columns=columns_to_drop)
        
    return combined_df

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Combine data from multiple Spotify Charts CSV files. The filenames are expected to be in the format 'regional-<region_code>-daily-<YYYY-MM-DD>.csv'"
    )

    parser.add_argument(
        "-i",
        "--input_dir",
        type=str,
        help="the directory containing downloaded Spotify Charts CSV files",
        required=True,
    )
    parser.add_argument(
        "-o",
        "--output_file",
        type=str,
        help="the filename of the output file (either csv or parquet)",
        required=True,
    )

    parser.add_argument(
        "-s",
        "--start_date",
        type=str,
        help="the start date (inclusive) of the date range to include in the output file (format: YYYY-MM-DD)",
        required=True,
    )
    parser.add_argument(
        "-e",
        "--end_date",
        type=str,
        help="the end date (inclusive) of the date range to include in the output file (format: YYYY-MM-DD)",
        required=True,
    )
    parser.add_argument(
        "-d",
        "--drop_redundant_columns",
        action="store_true",
        help="drop redundant columns that can be derived from within dataset or data from Spotify API ('artist_names', 'track_name', 'source', 'peak_rank', 'previous_rank', 'days_on_chart')",
    )

    args = parser.parse_args()
    
    out_path = args.output_file
    file_ext = out_path.split(".")[-1]
    
    if file_ext not in ["csv", "parquet"]:
        raise ValueError(f"Unsupported file extension: '.{file_ext}'")

    input_dir = args.input_dir
    
    try:
        start_date = (
            pd.to_datetime(args.start_date) if args.start_date is not None else None
        )
    except ValueError as e:
        print(f"Invalid start date filter provided: {args.start_date}")
        exit(1)

    try:
        end_date = (
            pd.to_datetime(args.end_date) if args.end_date is not None else None
        )
    except ValueError as e:
        print(f"Invalid end date filter provided: {args.end_date}")
        exit(1)
        
    drop_redundant_columns = args.drop_redundant_columns
    
    combined_data = combine_csv_files(
        input_dir, start_date, end_date, drop_redundant_columns
    )
    
    print(f"Combined data has {len(combined_data)} rows")
    print(
        f"Combined data contains {len(combined_data.track_id.unique())} unique tracks"
    )
    print(
        f"Combined data contains {len(combined_data.region_code.unique())} unique regions"
    )
    print(f"Combined data contains {len(combined_data.date.unique())} unique dates")
    print(f"First date is {combined_data.date.min()}")
    print(f"Last date is {combined_data.date.max()}")

    print(f'Saving combined data to "{out_path}"')

    output_dir = os.path.dirname(out_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if file_ext == "parquet":
        combined_data.to_parquet(out_path, index=False)
    else:
        combined_data.to_csv(out_path)