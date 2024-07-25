# Add these lines in the __init__ method, inside the data_tab section

# Time scale label and entry
self.time_scale_label = Label(self.data_tab, text="Time Scale:")
self.time_scale_label.grid(row=3, column=0)

self.time_scale = StringVar()
self.time_scale_entry = Entry(self.data_tab, textvariable=self.time_scale)
self.time_scale_entry.grid(row=3, column=1)

# Reset data button
self.reset_data_button = Button(self.data_tab, text="Reset Data", command=self.reset_data)
self.reset_data_button.grid(row=4, column=2)

def reset_data(self):
    self.df_combined = None  # Reset the combined dataframe
    self.update_columns()  # Update columns to clear any loaded data
    messagebox.showinfo("Info", "Data reset")

def generate_plot(self):
    try:
        time_scale = self.time_scale.get()
        if time_scale:
            time_scale = float(time_scale)
        else:
            time_scale = 1.0  # Default time scale

        fig, ax1 = plt.subplots(figsize=(10, 6))
        ax2 = None
        secondary_y = False
        primary_y_units = self.plot_data[0][3]

        for (x_col, y_col, x_units, y_units) in self.plot_data:
            x_data = self.df_combined[x_col] * time_scale  # Apply the time scale
            if y_units == primary_y_units:
                ax1.plot(x_data, self.df_combined[y_col], label=f'{y_col} ({y_units})')
                ax1.set_xlabel(f'{self.x_axis_label} ({x_units})')
                ax1.set_ylabel(f'{self.y_axis_label} ({primary_y_units})')
            else:
                if not ax2:
                    ax2 = ax1.twinx()
                    secondary_y = True
                ax2.plot(x_data, self.df_combined[y_col], label=f'{y_col} ({y_units})', linestyle='dashed')
                ax2.set_ylabel(f'{self.y2_axis_label} ({y_units})')
        
        ax1.legend(loc='upper left')
        if ax2:
            ax2.legend(loc='upper right')

        plt.title(self.plot_title)
        plt.grid(True)
        plt.show()
    except Exception as e:
        messagebox.showerror("Error", str(e))