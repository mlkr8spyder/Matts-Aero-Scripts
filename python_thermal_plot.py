import pandas as pd
import matplotlib.pyplot as plt
import os

def sanitize_sheet_name(name):
    return ''.join(e if e.isalnum() else '_' for e in name)

def load_data(filename):
    xls = pd.ExcelFile(filename)
    data = {}
    for sheet_name in xls.sheet_names:
        sanitized_name = sanitize_sheet_name(sheet_name)
        data[sanitized_name] = pd.read_excel(filename, sheet_name=sheet_name)
    return data

def plot_data(data, sheet_name):
    sanitized_sheet_name = sanitize_sheet_name(sheet_name)
    sheet_data = data[sanitized_sheet_name]

    if 'Time' not in sheet_data.columns:
        raise ValueError(f'The header "Time" does not exist in the sheet "{sheet_name}".')

    if len(sheet_data.columns) < 14:
        raise ValueError(f'The sheet "{sheet_name}" does not contain at least 14 columns.')

    # Extract x and y data
    x_data = sheet_data['Time'] / 3600
    y_data = sheet_data.iloc[:, -5:]
    y_headers = y_data.columns

    # Create a figure and set its size
    fig, ax = plt.subplots(figsize=(11.92, 5.81))

    colors = plt.cm.get_cmap('tab10').colors

    # Plot the first three fluid groups
    for j in range(3):
        ax.plot(x_data, y_data.iloc[:, j], label=y_headers[j], color=colors[j], linewidth=2)

    # Plot the last two columns with the same color but different styles
    ax.plot(x_data, y_data.iloc[:, 3], label='LFL', color=colors[0], linewidth=2, linestyle='--')
    ax.plot(x_data, y_data.iloc[:, 4], label='UFL', color=colors[0], linewidth=2, linestyle='-')

    # Customize plot
    ax.set_xlabel('Time')
    ax.set_ylabel('Temperature')
    ax.set_title(f'The Relationship Between Fluid Temperature and Elapsed Mission Time: {sheet_name}')
    ax.legend(loc='upper left', bbox_to_anchor=(1, 1))

    # Adjust axes limits
    ax.set_xlim([x_data.min(), x_data.max()])
    ax.set_ylim([y_data.min().min(), y_data.max().max()])

    # Define folder paths
    fig_folder = 'figures'
    png_folder = 'exported_pngs'

    # Create folders if they don't exist
    os.makedirs(fig_folder, exist_ok=True)
    os.makedirs(png_folder, exist_ok=True)

    # Save the figure in different formats
    fig_filename = f'plot_{sanitized_sheet_name}'
    fig.savefig(os.path.join(fig_folder, f'{fig_filename}.png'))
    fig.savefig(os.path.join(png_folder, f'{fig_filename}.png'), dpi=300)

    plt.close(fig)

# Load data from the Excel file
filename = 'example_data.xlsx'
data = load_data(filename)

# Plot data for each sheet
for sheet_name in data.keys():
    plot_data(data, sheet_name)
