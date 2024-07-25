import pandas as pd
import matplotlib.pyplot as plt
from tkinter import Tk, Label, Entry, Button, StringVar, OptionMenu, filedialog, messagebox
import os

class DataPlotterApp:
    def __init__(self, master):
        self.master = master
        master.title("Data Plotter")

        self.file_path = r"C:\Users\mlkr8\OneDrive\Desktop\Projects\Aero Scripts\Matts-Aero-Scripts"
        
        self.df = None  # Initialize the dataframe as None
        self.df_combined = None  # Initialize the combined dataframe as None
        
        # File name entry
        self.file_label = Label(master, text="File Name:")
        self.file_label.grid(row=0, column=0)

        self.file_name = StringVar()
        self.file_entry = Entry(master, textvariable=self.file_name)
        self.file_entry.grid(row=0, column=1)

        self.load_button = Button(master, text="Load File", command=self.load_file)
        self.load_button.grid(row=0, column=2)

        # Add another dataset
        self.add_file_button = Button(master, text="Add Another Dataset", command=self.add_file)
        self.add_file_button.grid(row=1, column=2)

        # Column selectors
        self.x_label = Label(master, text="X-axis Column:")
        self.x_label.grid(row=2, column=0)

        self.x_column = StringVar()
        self.x_menu = OptionMenu(master, self.x_column, ())
        self.x_menu.grid(row=2, column=1)

        self.y_label = Label(master, text="Y-axis Column:")
        self.y_label.grid(row=3, column=0)

        self.y_column = StringVar()
        self.y_menu = OptionMenu(master, self.y_column, ())
        self.y_menu.grid(row=3, column=1)

        # Axis units
        self.x_units_label = Label(master, text="X-axis Units:")
        self.x_units_label.grid(row=4, column=0)

        self.x_units = StringVar()
        self.x_units_entry = Entry(master, textvariable=self.x_units)
        self.x_units_entry.grid(row=4, column=1)

        self.y_units_label = Label(master, text="Y-axis Units:")
        self.y_units_label.grid(row=5, column=0)

        self.y_units = StringVar()
        self.y_units_entry = Entry(master, textvariable=self.y_units)
        self.y_units_entry.grid(row=5, column=1)

        # Plot button
        self.plot_button = Button(master, text="Generate Plot", command=self.generate_plot)
        self.plot_button.grid(row=6, column=1)

        # Save dataframe button
        self.save_df_button = Button(master, text="Save DataFrame", command=self.save_dataframe)
        self.save_df_button.grid(row=7, column=1)

        # Save plot button
        self.save_plot_button = Button(master, text="Save Plot", command=self.save_plot)
        self.save_plot_button.grid(row=8, column=1)

    def load_file(self):
        try:
            file_name = self.file_entry.get()
            full_path = self.file_path + "/" + file_name + ".txt"
            self.df = pd.read_csv(full_path, delim_whitespace=True)
            self.df_combined = self.df.copy()  # Initialize combined dataframe as the first dataframe
            self.update_columns()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def add_file(self):
        try:
            file_name = self.file_entry.get()
            full_path = self.file_path + "/" + file_name + ".txt"
            df_new = pd.read_csv(full_path, delim_whitespace=True)
            
            # Remove duplicate columns
            duplicate_columns = [col for col in df_new.columns if col in self.df_combined.columns]
            df_new = df_new.drop(columns=duplicate_columns)
            
            # Combine dataframes
            self.df_combined = pd.concat([self.df_combined, df_new], axis=1)
            self.update_columns()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def update_columns(self):
        columns = self.df_combined.columns.tolist()

        self.x_menu['menu'].delete(0, 'end')
        self.y_menu['menu'].delete(0, 'end')

        for col in columns:
            self.x_menu['menu'].add_command(label=col, command=lambda value=col: self.x_column.set(value))
            self.y_menu['menu'].add_command(label=col, command=lambda value=col: self.y_column.set(value))

        if columns:
            self.x_column.set(columns[0])
            self.y_column.set(columns[1])

    def generate_plot(self):
        try:
            x_col = self.x_column.get()
            y_col = self.y_column.get()
            x_units = self.x_units.get()
            y_units = self.y_units.get()

            plt.figure(figsize=(10, 6))
            plt.plot(self.df_combined[x_col], self.df_combined[y_col], label=f'{y_col} vs {x_col}')
            plt.xlabel(f'{x_col} ({x_units})')
            plt.ylabel(f'{y_col} ({y_units})')
            plt.title(f'{y_col} vs {x_col}')
            plt.legend()
            plt.grid(True)
            plt.show()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def save_dataframe(self):
        try:
            folder_path = os.path.join(self.file_path, "Post_Processing")
            os.makedirs(folder_path, exist_ok=True)
            file_name = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
            if file_name:
                save_path = os.path.join(folder_path, os.path.basename(file_name))
                self.df_combined.to_excel(save_path, index=False)
                messagebox.showinfo("Success", f"DataFrame saved as {save_path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def save_plot(self):
        try:
            folder_path = os.path.join(self.file_path, "Post_Processing")
            os.makedirs(folder_path, exist_ok=True)
            file_name = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")])
            if file_name:
                save_path = os.path.join(folder_path, os.path.basename(file_name))
                x_col = self.x_column.get()
                y_col = self.y_column.get()
                x_units = self.x_units.get()
                y_units = self.y_units.get()
                
                plt.figure(figsize=(10, 6))
                plt.plot(self.df_combined[x_col], self.df_combined[y_col], label=f'{y_col} vs {x_col}')
                plt.xlabel(f'{x_col} ({x_units})')
                plt.ylabel(f'{y_col} ({y_units})')
                plt.title(f'{y_col} vs {x_col}')
                plt.legend()
                plt.grid(True)
                plt.savefig(save_path)
                plt.close()
                messagebox.showinfo("Success", f"Plot saved as {save_path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    root = Tk()
    app = DataPlotterApp(root)
    root.mainloop()
