def parse_file(file_path):
    import re

    with open(file_path, 'r') as file:

        lines = file.readlines()
    
    part_data = {}
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
                part_data[part_number] = {'location': current_location, 'thickness': None}
            # Check if the line is a thickness
            elif re.match(r'^\d*\.?\d+$', stripped_line):
                thickness = float(stripped_line)
                # Ensure part_number is defined before updating thickness
                if part_number:
                    part_data[part_number]['thickness'] = thickness
                else:
                    print(f"Warning: Found thickness {thickness} without preceding part number")

    return part_data

# Example usage
file_path = r'C:\Users\mlkr8\OneDrive\Desktop\Projects\Aero Scripts\Matts-Aero-Scripts\example.txt'
parsed_data = parse_file(file_path)
print(parsed_data)
