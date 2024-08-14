import pandas as pd
import numpy as np

# Load CSV file
file_path = "your_file.csv"  # Replace with your file path
df = pd.read_csv(file_path)

# Convert the time column to a pandas datetime format (assuming time is in seconds)
df['time'] = pd.to_datetime(df['time'], unit='s')

# Set the time as the DataFrame index
df.set_index('time', inplace=True)

# Resample the data to 0.1-second intervals and calculate the mean for each parameter
resampled_df = df.resample('100ms').mean()

# Reset the index to get 'time' back as a column
resampled_df.reset_index(inplace=True)

# Save the resampled data to a new CSV file
resampled_df.to_csv("resampled_data.csv", index=False)

print("Resampled data saved to resampled_data.csv")