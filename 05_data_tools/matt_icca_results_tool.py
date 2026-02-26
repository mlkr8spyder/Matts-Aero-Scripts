import pandas as pd
import matplotlib.pyplot as plt
from tkinter import Tk, Label, Entry, Button, StringVar, OptionMenu, filedialog, messagebox, ttk
import os

class DataPlotterApp:
    def __init__(self, master):
        self.master = master
        master.title("Data Plotter")

        self.file_path = r"C:\Users\mlkr8\OneDrive\Desktop\Projects\Aero Scripts\Matts-Aero-Scripts"
        
        self.df_combined = None  # Initialize the combined dataframe as None
        self.plot_data = []  # List to hold plot data information
        
        self.tab_control = ttk.Notebook(master)
        
        self.data_tab = ttk.Frame(self.tab_control)
        self.plot_tab = ttk.Frame(self.tab_control)
        
        self.tab_control.add(self.data_tab, text='Data')
        self.tab_control.add(self.plot_tab, text='Plot')
        
        self.tab_control.pack(expand=1, fill='both')
        
        # Data tab
        self.file_label = Label(self.data_tab, text="File Name:")
        self.file_label.grid(row=0, column=0)

        self.file_name = StringVar()
        self.file_entry = Entry(self.data_tab, textvariable=self.file_name)
        self.file_entry.grid(row=0, column=1)

        self.load_button = Button(self.data_tab, text="Load File", command=self.load_file)
        self.load_button.grid(row=0, column=2)

        self.add_file_button = Button(self.data_tab, text="Add Another Dataset", command=self.add_file)
        self.add_file_button.grid(row=1, column=2)

        self.save_df_button = Button(self.data_tab, text="Save DataFrame", command=self.save_dataframe)
        self.save_df_button.grid(row=3, column=1)
        
        self.plot_title = "Combined Plot"
        self.x_axis_label = "X-axis"
        self.y_axis_label = "Y-axis"
        self.y2_axis_label = "Y2-axis"
        
        # Plot tab
        self.x_label = Label(self.plot_tab, text="X-axis Column:")
        self.x_label.grid(row=0, column=0)

        self.x_column = StringVar()
        self.x_menu = OptionMenu(self.plot_tab, self.x_column, ())
        self.x_menu.grid(row=0, column=1)

        self.y_label = Label(self.plot_tab, text="Y-axis Column:")
        self.y_label.grid(row=1, column=0)

        self.y_column = StringVar()
        self.y_menu = OptionMenu(self.plot_tab, self.y_column, ())
        self.y_menu.grid(row=1, column=1)
        
        self.x_units_label = Label(self.plot_tab, text="X-axis Units:")
        self.x_units_label.grid(row=2, column=0)

        self.x_units = StringVar()
        self.x_units_entry = Entry(self.plot_tab, textvariable=self.x_units)
        self.x_units_entry.grid(row=2, column=1)

        self.y_units_label = Label(self.plot_tab, text="Y-axis Units:")
        self.y_units_label.grid(row=3, column=0)

        self.y_units = StringVar()
        self.y_units_entry = Entry(self.plot_tab, textvariable=self.y_units)
        self.y_units_entry.grid(row=3, column=1)

        self.plot_button = Button(self.plot_tab, text="Add to Plot", command=self.add_to_plot)
        self.plot_button.grid(row=4, column=1)
        
        self.generate_plot_button = Button(self.plot_tab, text="Generate Plot", command=self.generate_plot)
        self.generate_plot_button.grid(row=5, column=1)
        
        self.save_plot_button = Button(self.plot_tab, text="Save Plot", command=self.save_plot)
        self.save_plot_button.grid(row=4, column=0)

        self.clear_plot_button = Button(self.plot_tab, text="Clear Plot", command=self.clear_plot)
        self.clear_plot_button.grid(row=5, column=0)
        
        self.rename_label = Label(self.plot_tab, text="Select element to rename:")
        self.rename_label.grid(row=8, column=0)

        self.rename_option = StringVar()
        self.rename_option_menu = OptionMenu(self.plot_tab, self.rename_option, "Title", "X-axis", "Y-axis", "Y2-axis")
        self.rename_option_menu.grid(row=8, column=1)

        self.rename_entry_label = Label(self.plot_tab, text="New name:")
        self.rename_entry_label.grid(row=9, column=0)

        self.rename_entry = Entry(self.plot_tab)
        self.rename_entry.grid(row=9, column=1)

        self.rename_button = Button(self.plot_tab, text="Rename", command=self.rename_element)
        self.rename_button.grid(row=9, column=2)
        
    def load_file(self):
        try:
            file_name = self.file_entry.get()
            full_path = self.file_path + "/" + file_name + ".txt"
            self.df_combined = pd.read_csv(full_path, delim_whitespace=True)
            
            # Interpolate non-numeric values
            for col in self.df_combined.columns:
                self.df_combined[col] = pd.to_numeric(self.df_combined[col], errors='coerce')
                self.df_combined[col].interpolate(method='linear', inplace=True)
            
            self.update_columns()
        except Exception as e:
            messagebox.showerror("Error", str(e))


    def add_file(self):
        try:
            file_name = self.file_entry.get()
            full_path = self.file_path + "/" + file_name + ".txt"
            df_new = pd.read_csv(full_path, delim_whitespace=True)
            
            # Interpolate non-numeric values
            for col in df_new.columns:
                df_new[col] = pd.to_numeric(df_new[col], errors='coerce')
                df_new[col].interpolate(method='linear', inplace=True)
            
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

    def add_to_plot(self):
        try:
            x_col = self.x_column.get()
            y_col = self.y_column.get()
            x_units = self.x_units.get()
            y_units = self.y_units.get()
            self.plot_data.append((x_col, y_col, x_units, y_units))
            messagebox.showinfo("Info", f"Added {y_col} vs {x_col} to plot")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def generate_plot(self):
        try:
            fig, ax1 = plt.subplots(figsize=(10, 6))
            ax2 = None
            secondary_y = False
            primary_y_units = self.plot_data[0][3]

            for (x_col, y_col, x_units, y_units) in self.plot_data:
                if y_units == primary_y_units:
                    ax1.plot(self.df_combined[x_col], self.df_combined[y_col], label=f'{y_col} ({y_units})')
                    ax1.set_xlabel(f'{self.x_axis_label} ({x_units})')
                    ax1.set_ylabel(f'{self.y_axis_label} ({primary_y_units})')
                else:
                    if not ax2:
                        ax2 = ax1.twinx()
                        secondary_y = True
                    ax2.plot(self.df_combined[x_col], self.df_combined[y_col], label=f'{y_col} ({y_units})', linestyle='dashed')
                    ax2.set_ylabel(f'{self.y2_axis_label} ({y_units})')
            
            ax1.legend(loc='upper left')
            if ax2:
                ax2.legend(loc='upper right')

            plt.title(self.plot_title)
            plt.grid(True)
            plt.show()
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def clear_plot(self):
        self.plot_data = []  # Reset the plot data
        plt.close('all')  # Close all matplotlib figures
        messagebox.showinfo("Info", "Plot cleared")
    
    def rename_element(self):
        element = self.rename_option.get()
        new_name = self.rename_entry.get()
        
        if not new_name:
            messagebox.showerror("Error", "New name cannot be empty")
            return
        
        if element == "Title":
            self.plot_title = new_name
        elif element == "X-axis":
            self.x_axis_label = new_name
        elif element == "Y-axis":
            self.y_axis_label = new_name
        elif element == "Y2-axis":
            self.y2_axis_label = new_name
        
        messagebox.showinfo("Info", f"{element} renamed to {new_name}")
    
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
                
                fig, ax1 = plt.subplots(figsize=(10, 6))
                ax2 = None
                secondary_y = False
                primary_y_units = self.plot_data[0][3]

                for (x_col, y_col, x_units, y_units) in self.plot_data:
                    if y_units == primary_y_units:
                        ax1.plot(self.df_combined[x_col], self.df_combined[y_col], label=f'{y_col} ({y_units})')
                        ax1.set_xlabel(f'{x_col} ({x_units})')
                        ax1.set_ylabel(f'{self.plot_data[0][1]} ({primary_y_units})')
                    else:
                        if not ax2:
                            ax2 = ax1.twinx()
                            secondary_y = True
                        ax2.plot(self.df_combined[x_col], self.df_combined[y_col], label=f'{y_col} ({y_units})', linestyle='dashed')
                        ax2.set_ylabel(f'{y_col} ({y_units})')
                
                ax1.legend(loc='upper left')
                if ax2:
                    ax2.legend(loc='upper right')

                plt.title('Combined Plot')
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
