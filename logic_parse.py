import re

def extract_phrases_from_brackets(file_path):
    with open(file_path, 'r') as file:
        text = file.read()
    
    # Regular expression to find phrases within brackets
    pattern = re.compile(r'\[(.*?)\]')
    matches = pattern.findall(text)
    
    # Remove duplicates by converting the list to a set and back to a list
    unique_phrases = list(set(matches))
    
    return unique_phrases

def write_phrases_to_file(phrases, output_path):
    with open(output_path, 'w') as file:
        for phrase in phrases:
            file.write(f"{phrase}\n")

# Example usage
input_file_path = 'your_file.txt'  # Replace with the path to your input text file
output_file_path = 'output_phrases.txt'  # Replace with the desired path for the output text file

phrases = extract_phrases_from_brackets(input_file_path)
write_phrases_to_file(phrases, output_file_path)