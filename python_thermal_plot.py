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
    return data, xls.sheet_names

def plot_data(data, original_sheet_name, sanitized_sheet_name, fig_folder, png_folder):
    sheet_data = data[sanitized_sheet_name]

    if 'Time' not in sheet_data.columns:
        raise ValueError(f'The header "Time" does not exist in the sheet "{original_sheet_name}".')

    if len(sheet_data.columns) < 14:
        raise ValueError(f'The sheet "{original_sheet_name}" does not contain at least 14 columns.')

    # Extract x and y data
    x_data = sheet_data['Time'] / 3600  # Convert seconds to hours
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

    # Add annotations for the 13th and 14th columns
    ax.annotate(
        'LFL: ' + y_headers[3],
        xy=(x_data.iloc[-1], y_data.iloc[-1, 3]),
        xytext=(x_data.iloc[-1], y_data.iloc[-1, 3] + 5),
        arrowprops=dict(facecolor='black', arrowstyle='->'),
        bbox=dict(boxstyle='round,pad=0.3', edgecolor='black', facecolor='white')
    )
    ax.annotate(
        'UFL: ' + y_headers[4],
        xy=(x_data.iloc[-1], y_data.iloc[-1, 4]),
        xytext=(x_data.iloc[-1], y_data.iloc[-1, 4] + 5),
        arrowprops=dict(facecolor='black', arrowstyle='->'),
        bbox=dict(boxstyle='round,pad=0.3', edgecolor='black', facecolor='white')
    )

    # Customize plot
    ax.set_xlabel('Time (hours)')
    ax.set_ylabel('Temperature')
    ax.set_title(f'The Relationship Between Fluid Temperature and Elapsed Mission Time: {original_sheet_name}')
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05), ncol=3)
    ax.grid(True)

    # Adjust axes limits
    ax.set_xlim([x_data.min(), x_data.max()])
    ax.set_ylim([y_data.min().min(), y_data.max().max()])

    # Save the figure in different formats
    fig_filename = f'plot_{sanitized_sheet_name}'
    fig.savefig(os.path.join(fig_folder, f'{fig_filename}.png'))
    fig.savefig(os.path.join(png_folder, f'{fig_filename}.png'), dpi=300)
    fig.savefig(os.path.join(png_folder, f'{fig_filename}.pdf'))

    plt.close(fig)

def main():
    # Load data from the Excel file
    filename = 'example_data.xlsx'
    data, sheet_names = load_data(filename)

    # Define folder paths
    fig_folder = 'figures'
    png_folder = 'exported_pngs'

    # Create folders if they don't exist
    os.makedirs(fig_folder, exist_ok=True)
    os.makedirs(png_folder, exist_ok=True)

    # Plot data for each sheet
    for sheet_name in sheet_names:
        sanitized_sheet_name = sanitize_sheet_name(sheet_name)
        plot_data(data, sheet_name, sanitized_sheet_name, fig_folder, png_folder)

if __name__ == "__main__":
    main()
