def parse_file_with_materials(file_path):
    import re

    with open(file_path, 'r') as file:
        lines = file.readlines()
    
    location_data = {}
    current_location = None
    part_number = None

    for line in lines:
        stripped_line = line.strip()
        if stripped_line:
            # Check if the line is a header (location)
            if not any(char.isdigit() for char in stripped_line):
                current_location = stripped_line
            # Check if the line is a part number
            elif any(char.isdigit() for char in stripped_line) and any(char.isalpha() for char in stripped_line):
                part_number = stripped_line
            # Check if the line is a material
            elif re.match(r'^[A-Za-z_]+$', stripped_line):
                material = stripped_line
                # Ensure part_number is defined before adding to the list
                if part_number:
                    location_data[current_location].append((part_number, material))
                    part_number = None  # Reset part number after adding the pair
                else:
                    print(f"Warning: Found material {material} without preceding part number")

    return location_data

# Example usage
file_path = r'C:\Users\mlkr8\OneDrive\Desktop\Projects\Aero Scripts\Matts-Aero-Scripts\material.txt'
parsed_data = parse_file_with_materials(file_path)
print(parsed_data)
