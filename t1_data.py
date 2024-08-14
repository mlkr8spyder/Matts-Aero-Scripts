import pandas as pd
import matplotlib.pyplot as plt

# Load the resampled data
resampled_df = pd.read_csv("resampled_data.csv")

# Normalize the time column by subtracting the first time value
resampled_df['time'] = resampled_df['time'] - resampled_df['time'].iloc[0]

# Define the threshold value for filtering
threshold_value = 10  # Replace with your desired threshold

# Filter out rows where the value in 'column2' exceeds the threshold
filtered_df = resampled_df[resampled_df['column2'] <= threshold_value]

# Save the filtered data to a new CSV file
filtered_df.to_csv("filtered_data.csv", index=False)

# Plot each parameter over time from the filtered DataFrame
plt.figure(figsize=(10, 6))

for column in filtered_df.columns:
    if column != 'time':  # Exclude the time column from plotting
        plt.plot(filtered_df['time'], filtered_df[column], label=column)

plt.xlabel('Time (seconds)')
plt.ylabel('Parameter Value')
plt.title('Filtered Parameters over Normalized Time')
plt.legend()
plt.grid(True)

# Show the plot
plt.show()

print("Filtered data saved to filtered_data.csv")