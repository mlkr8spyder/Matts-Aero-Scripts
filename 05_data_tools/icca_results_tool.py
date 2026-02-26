import pandas as pd

def load_icca_file(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()
    
    split_lines = [line.split() for line in lines]
    
    df = pd.DataFrame(split_lines)
    
    return df

file_name = r'C:\Users\mlkr8\OneDrive\Desktop\Projects\Aero Scripts\Matts-Aero-Scripts\icca_results_test.txt'

icca_df = pd.read_csv(file_name, delim_whitespace=True)

print(icca_df)