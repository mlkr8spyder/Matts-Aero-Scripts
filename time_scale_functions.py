# Add these lines in the __init__ method, inside the plot_tab section

# Start time label and entry
self.start_time_label = Label(self.plot_tab, text="Start Time:")
self.start_time_label.grid(row=11, column=0)

self.start_time = StringVar()
self.start_time_entry = Entry(self.plot_tab, textvariable=self.start_time)
self.start_time_entry.grid(row=11, column=1)

# End time label and entry
self.end_time_label = Label(self.plot_tab, text="End Time:")
self.end_time_label.grid(row=12, column=0)

self.end_time = StringVar()
self.end_time_entry = Entry(self.plot_tab, textvariable=self.end_time)
self.end_time_entry.grid(row=12, column=1)

# Reset data button
self.reset_data_button = Button(self.data_tab, text="Reset Data", command=self.reset_data)
self.reset_data_button.grid(row=4, column=2)

def reset_data(self):
    self.df_combined = None  # Reset the combined dataframe
    self.update_columns()  # Update columns to clear any loaded data
    messagebox.showinfo("Info", "Data reset")

def generate_plot(self):
    try:
        start_time = self.start_time.get()
        end_time = self.end_time.get()

        if start_time:
            start_time = float(start_time)
        else:
            start_time = self.df_combined['Time'].min()  # Default to min time

        if end_time:
            end_time = float(end_time)
        else:
            end_time = self.df_combined['Time'].max()  # Default to max time

        # Filter the dataframe based on the specified time range
        df_filtered = self.df_combined[(self.df_combined['Time'] >= start_time) & (self.df_combined['Time'] <= end_time)]

        fig, ax1 = plt.subplots(figsize=(10, 6))
        ax2 = None
        secondary_y = False
        primary_y_units = self.plot_data[0][3]

        for (x_col, y_col, x_units, y_units) in self.plot_data:
            if y_units == primary_y_units:
                ax1.plot(df_filtered[x_col], df_filtered[y_col], label=f'{y_col} ({y_units})')
                ax1.set_xlabel(f'{self.x_axis_label} ({x_units})')
                ax1.set_ylabel(f'{self.y_axis_label} ({primary_y_units})')
            else:
                if not ax2:
                    ax2 = ax1.twinx()
                    secondary_y = True
                ax2.plot(df_filtered[x_col], df_filtered[y_col], label=f'{y_col} ({y_units})', linestyle='dashed')
                ax2.set_ylabel(f'{self.y2_axis_label} ({y_units})')
        
        ax1.legend(loc='upper left')
        if ax2:
            ax2.legend(loc='upper right')

        plt.title(self.plot_title)
        plt.grid(True)
        plt.show()
    except Exception as e:
        messagebox.showerror("Error", str(e))
        
def update_columns(self):
    if self.df_combined is not None:
        columns = self.df_combined.columns.tolist()
    else:
        columns = []

    self.x_menu['menu'].delete(0, 'end')
    self.y_menu['menu'].delete(0, 'end')

    for col in columns:
        self.x_menu['menu'].add_command(label=col, command=lambda value=col: self.x_column.set(value))
        self.y_menu['menu'].add_command(label=col, command=lambda value=col: self.y_column.set(value))

    if columns:
        self.x_column.set(columns[0])
        self.y_column.set(columns[1])
    else:
        self.x_column.set('')
        self.y_column.set('')