import matplotlib.pyplot as plt

def plot_histogram_with_stats(parts_dict, locations, material):
    """
    Plot histograms of thicknesses of parts with the specified locations and material,
    with the average and median thicknesses highlighted.

    Args:
    parts_dict (dict): The dictionary containing part information.
    locations (str or list): The aircraft location(s) to search for parts.
                             This can be either an array of specific locations or the string "All".
    material (str): The material to filter parts by.
    """

    def calculate_stats(thicknesses):
        import numpy as np
        average_thickness = np.mean(thicknesses)
        median_thickness = np.median(thicknesses)
        std_dev_thickness = np.std(thicknesses)
        return average_thickness, median_thickness, std_dev_thickness

    if locations == "All":
        unique_locations = set([details['aircraft_location'] for details in parts_dict.values() if 'aircraft_location' in details])
    else:
        unique_locations = locations

    thicknesses = []
    for details in parts_dict.values():
        if 'aircraft_location' in details and (locations == "All" or details['aircraft_location'] in unique_locations):
            if 'materials' in details and material in details['materials']:
                thicknesses.append(details['thickness'])

    fig, ax = plt.subplots(figsize=(10, 5))
    if thicknesses:
        average_thickness, median_thickness, std_dev_thickness = calculate_stats(thicknesses)
        ax.hist(thicknesses, bins=20, color='black', edgecolor='white')
        ax.axvline(average_thickness, color='red', linestyle='dashed', linewidth=1, label=f'Average: {average_thickness:.2f} in')
        ax.axvline(median_thickness, color='yellow', linestyle='solid', linewidth=1, label=f'Median: {median_thickness:.2f} in')
        ax.set_xlabel('Thickness (inches)')
        ax.set_ylabel('Frequency')
        ax.set_title(f'Histogram of Part Thicknesses (Material: {material})')
        ax.legend()
        total_samples = len(thicknesses)
        ax.annotate(f'N={total_samples}', xy=(0.95, 0.95), xycoords='axes fraction', fontsize=12, ha='right', va='top', bbox=dict(boxstyle='round,pad=0.3', edgecolor='black', facecolor='white'))
    else:
        ax.text(0.5, 0.5, "No parts found with specified criteria", horizontalalignment='center', verticalalignment='center', fontsize=12)

    plt.tight_layout()
    plt.show()
