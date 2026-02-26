import pandas as pd
import matplotlib.pyplot as plt
import os
import json

def sanitize_sheet_name(name):
    return ''.join(e if e.isalnum() else '_' for e in name)

def replace_strings_in_headers(headers, old_str, new_str):
    return [header.replace(old_str, new_str) for header in headers]

def load_data_from_json(json_filename):
    with open(json_filename, 'r') as f:
        json_data = json.load(f)
    data = {k: pd.DataFrame(v) for k, v in json_data['data'].items()}
    sheet_mapping = json_data['sheet_mapping']
    return data, sheet_mapping

def reformat_sheet_name(sheet_name):
    phrases = sheet_name.split(', ')
    phrase_mapping = {
        "run type": "Run Type",
        "exp": "Experiment",
        "test": "Test",
        "day type": "Day Type",
        "weekday": "Weekday",
        "weekend": "Weekend",
        "weekday%": "Weekday",
        "weekend%": "Weekend",
        "fluid type": "Fluid Type",
        "grp1": "Group 1",
        "grp2": "Group 2",
        "grp3": "Group 3"
        # Add more mappings as needed
    }
    
    readable_phrases = [phrase_mapping.get(phrase, phrase) for phrase in phrases]
    
    if len(readable_phrases) >= 3:
        return f"{readable_phrases[0]}: {readable_phrases[1]} for {readable_phrases[2]}"
    else:
        return sheet_name

import pandas as pd
import matplotlib.pyplot as plt
import os
import json

def sanitize_sheet_name(name):
    return ''.join(e if e.isalnum() else '_' for e in name)

def replace_strings_in_headers(headers, old_str, new_str):
    return [header.replace(old_str, new_str) for header in headers]

def reformat_sheet_name(sheet_name):
    phrases = sheet_name.split(', ')
    phrase_mapping = {
        "run type": "Run Type",
        "exp": "Experiment",
        "test": "Test",
        "day type": "Day Type",
        "weekday": "Weekday",
        "weekend": "Weekend",
        "weekday%": "Weekday",
        "weekend%": "Weekend",
        "fluid type": "Fluid Type",
        "grp1": "Group 1",
        "grp2": "Group 2",
        "grp3": "Group 3"
        # Add more mappings as needed
    }
    
    readable_phrases = [phrase_mapping.get(phrase, phrase) for phrase in phrases]
    
    if len(readable_phrases) >= 3:
        return f"{readable_phrases[0]}: {readable_phrases[1]} for {readable_phrases[2]}"
    else:
        return sheet_name

def plot_data(data, sheet_mapping, sanitized_sheet_name, fig_folder, png_folder):
    sheet_data = data[sanitized_sheet_name]
    original_sheet_name = sheet_mapping[sanitized_sheet_name]

    if 'Time' not in sheet_data.columns:
        raise ValueError(f'The header "Time" does not exist in the sheet "{original_sheet_name}".')

    if len(sheet_data.columns) < 14:
        raise ValueError(f'The sheet "{original_sheet_name}" does not contain at least 14 columns.')

    # Replace strings in column headers
    y_headers = sheet_data.columns[-5:]
    y_headers = replace_strings_in_headers(y_headers, 'OldString', 'NewString')  # Example

    # Extract x and y data
    x_data = sheet_data['Time'] / 3600  # Convert seconds to hours
    y_data = sheet_data.iloc[:, -5:]
    y_data.columns = y_headers  # Update column headers

    # Reformat the sheet name for the title
    readable_sheet_name = reformat_sheet_name(original_sheet_name)

    # Read the ninth column and find the max value
    ninth_column_header = sheet_data.columns[8]
    ninth_column_data = sheet_data.iloc[:, 8]
    ninth_column_max = ninth_column_data.max()

    # Create a figure and set its size
    fig, ax = plt.subplots(figsize=(15, 8))

    colors = plt.cm.get_cmap('tab10').colors

    # Plot the first three fluid groups
    for j in range(3):
        ax.plot(x_data, y_data.iloc[:, j], label=y_headers[j], color=colors[j], linewidth=2)

    # Plot the last two columns with the same color but different styles
    ax.plot(x_data, y_data.iloc[:, 3], label='LFL', color=colors[0], linewidth=2, linestyle='--')
    ax.plot(x_data, y_data.iloc[:, 4], label='UFL', color=colors[0], linewidth=2, linestyle='-')

    # Calculate positions for annotations
    annotation_positions = {
        "LFL": (x_data.iloc[len(x_data) // 2], y_data.iloc[len(y_data) // 2, 3]),
        "UFL": (x_data.iloc[len(x_data) // 2], y_data.iloc[len(y_data) // 2, 4]),
        "Max": (x_data.iloc[len(x_data) // 2], ninth_column_max)
    }

    # Add annotations for the 13th and 14th columns
    ax.annotate(
        f'LFL: {y_headers[3]}',
        xy=(x_data.iloc[0], y_data.iloc[0, 3]),
        xytext=(x_data.iloc[0] - (x_data.max() - x_data.min()) * 0.05, y_data.iloc[0, 3]),
        textcoords='data',
        arrowprops=dict(facecolor='black', arrowstyle='->'),
        bbox=dict(boxstyle='round,pad=0.3', edgecolor='black', facecolor='white')
    )
    ax.annotate(
        f'UFL: {y_headers[4]}',
        xy=(x_data.iloc[0], y_data.iloc[0, 4]),
        xytext=(x_data.iloc[0] - (x_data.max() - x_data.min()) * 0.05, y_data.iloc[0, 4]),
        textcoords='data',
        arrowprops=dict(facecolor='black', arrowstyle='->'),
        bbox=dict(boxstyle='round,pad=0.3', edgecolor='black', facecolor='white')
    )
    # Add annotation for the max value of the ninth column
    # Calculate max value, round it to two decimal places, and convert to percentage
    ninth_column_max = round(ninth_column_max * 100, 2)

    # Add annotation for the max value of the ninth column
    if ninth_column_max != 0:
        ax.annotate(
            f'Max {ninth_column_header}: {ninth_column_max}%',
            xy=(0.5, 0.95), xycoords='axes fraction',
            ha='center',
            bbox=dict(boxstyle='round,pad=0.3', edgecolor='blue', facecolor='white')
        )
    else:
        ax.annotate(
            f'All {ninth_column_header} values are 0',
            xy=(0.5, 0.95), xycoords='axes fraction',
            ha='center',
            bbox=dict(boxstyle='round,pad=0.3', edgecolor='blue', facecolor='white')
        )



    # Customize plot
    ax.set_xlabel('Time (hours)')
    ax.set_ylabel('Temperature')
    ax.set_title(f'The Relationship Between Fluid Temperature and Elapsed Mission Time: {readable_sheet_name}')
    legend = ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.1), ncol=3)
    ax.grid(True)

    # Adjust axes limits
    ax.set_xlim([x_data.min(), x_data.max()])
    ax.set_ylim([y_data.min().min(), y_data.max().max()])

    # Define folder paths
    os.makedirs(fig_folder, exist_ok=True)
    os.makedirs(png_folder, exist_ok=True)

    # Save the figure in different formats
    fig_filename = f'plot_{sanitized_sheet_name}'
    fig.savefig(os.path.join(fig_folder, f'{fig_filename}.png'), bbox_extra_artists=(legend,), bbox_inches='tight')
    fig.savefig(os.path.join(png_folder, f'{fig_filename}.png'), dpi=300, bbox_extra_artists=(legend,), bbox_inches='tight')
    fig.savefig(os.path.join(png_folder, f'{fig_filename}.pdf'), bbox_extra_artists=(legend,), bbox_inches='tight')

    plt.close(fig)

# Example main function
def main():
    # Load data from the JSON file
    json_filename = 'data.json'
    data, sheet_mapping = load_data_from_json(json_filename)

    # Define folder paths
    fig_folder = 'figures'
    png_folder = 'exported_pngs'

    # Plot data for each sheet
    for sanitized_sheet_name in data.keys():
        plot_data(data, sheet_mapping, sanitized_sheet_name, fig_folder, png_folder)

if __name__ == "__main__":
    main()


# Example main function
def main():
    # Load data from the JSON file
    json_filename = 'data.json'
    data, sheet_mapping = load_data_from_json(json_filename)

    # Define folder paths
    fig_folder = 'figures'
    png_folder = 'exported_pngs'

    # Plot data for each sheet
    for sanitized_sheet_name in data.keys():
        plot_data(data, sheet_mapping, sanitized_sheet_name, fig_folder, png_folder)

if __name__ == "__main__":
    main()
