import tkinter as tk
from tkinter import ttk

# Sample fuel properties (density in kg/m^3, specific heat capacity in J/(kg·K))
fuel_properties = {
    'Jet A': {'Density': 804, 'Specific Heat Capacity': 2.02},
    'Jet A-1': {'Density': 800, 'Specific Heat Capacity': 2.01},
    'JP-8': {'Density': 780, 'Specific Heat Capacity': 2.05},
    'AVGAS': {'Density': 720, 'Specific Heat Capacity': 2.10}
}

class FuelPropertiesCalculator:
    def __init__(self, root):
        self.root = root
        self.root.title("Aviation Fuel Properties Calculator")
        
        # Create tabs
        self.tab_control = ttk.Notebook(root)
        
        self.create_fuel_properties_tab()
        self.create_unit_conversion_tab()
        
        self.tab_control.pack(expand=1, fill="both")
    
    def create_fuel_properties_tab(self):
        tab1 = ttk.Frame(self.tab_control)
        self.tab_control.add(tab1, text="Fuel Properties")
        
        ttk.Label(tab1, text="Select Fuel:").grid(column=0, row=0, padx=10, pady=10)
        
        self.fuel_var = tk.StringVar()
        fuel_options = list(fuel_properties.keys())
        self.fuel_dropdown = ttk.Combobox(tab1, textvariable=self.fuel_var, values=fuel_options)
        self.fuel_dropdown.grid(column=1, row=0, padx=10, pady=10)
        self.fuel_dropdown.bind("<<ComboboxSelected>>", self.display_properties)
        
        ttk.Label(tab1, text="Density (kg/m^3):").grid(column=0, row=1, padx=10, pady=10)
        self.density_label = ttk.Label(tab1, text="")
        self.density_label.grid(column=1, row=1, padx=10, pady=10)
        
        ttk.Label(tab1, text="Specific Heat Capacity (J/(kg·K)):").grid(column=0, row=2, padx=10, pady=10)
        self.heat_capacity_label = ttk.Label(tab1, text="")
        self.heat_capacity_label.grid(column=1, row=2, padx=10, pady=10)
    
    def display_properties(self, event):
        fuel = self.fuel_var.get()
        if fuel in fuel_properties:
            properties = fuel_properties[fuel]
            self.density_label.config(text=str(properties['Density']))
            self.heat_capacity_label.config(text=str(properties['Specific Heat Capacity']))
        else:
            self.density_label.config(text="")
            self.heat_capacity_label.config(text="")
    
    def create_unit_conversion_tab(self):
        tab2 = ttk.Frame(self.tab_control)
        self.tab_control.add(tab2, text="Unit Conversion")
        
        # Volumetric flow rate conversion
        ttk.Label(tab2, text="Volumetric Flow Rate (m^3/s):").grid(column=0, row=0, padx=10, pady=10)
        self.flow_rate_entry = ttk.Entry(tab2)
        self.flow_rate_entry.grid(column=1, row=0, padx=10, pady=10)
        
        ttk.Button(tab2, text="Convert to L/min", command=self.convert_flow_rate).grid(column=2, row=0, padx=10, pady=10)
        self.flow_rate_result = ttk.Label(tab2, text="")
        self.flow_rate_result.grid(column=3, row=0, padx=10, pady=10)
        
        # Density conversion
        ttk.Label(tab2, text="Density (kg/m^3):").grid(column=0, row=1, padx=10, pady=10)
        self.density_entry = ttk.Entry(tab2)
        self.density_entry.grid(column=1, row=1, padx=10, pady=10)
        
        ttk.Button(tab2, text="Convert to g/cm^3", command=self.convert_density).grid(column=2, row=1, padx=10, pady=10)
        self.density_result = ttk.Label(tab2, text="")
        self.density_result.grid(column=3, row=1, padx=10, pady=10)
        
        # K factor calculation
        ttk.Label(tab2, text="Viscosity (Pa·s):").grid(column=0, row=2, padx=10, pady=10)
        self.viscosity_entry = ttk.Entry(tab2)
        self.viscosity_entry.grid(column=1, row=2, padx=10, pady=10)
        
        ttk.Label(tab2, text="Density (kg/m^3) for K factor:").grid(column=0, row=3, padx=10, pady=10)
        self.k_density_entry = ttk.Entry(tab2)
        self.k_density_entry.grid(column=1, row=3, padx=10, pady=10)
        
        ttk.Button(tab2, text="Calculate K factor", command=self.calculate_k_factor).grid(column=2, row=3, padx=10, pady=10)
        self.k_factor_result = ttk.Label(tab2, text="")
        self.k_factor_result.grid(column=3, row=3, padx=10, pady=10)
        
        # Head pressure calculation
        ttk.Label(tab2, text="Flow rate (m^3/s) for head pressure:").grid(column=0, row=4, padx=10, pady=10)
        self.head_flow_rate_entry = ttk.Entry(tab2)
        self.head_flow_rate_entry.grid(column=1, row=4, padx=10, pady=10)
        
        ttk.Label(tab2, text="Density (kg/m^3) for head pressure:").grid(column=0, row=5, padx=10, pady=10)
        self.head_density_entry = ttk.Entry(tab2)
        self.head_density_entry.grid(column=1, row=5, padx=10, pady=10)
        
        ttk.Button(tab2, text="Calculate Head Pressure", command=self.calculate_head_pressure).grid(column=2, row=5, padx=10, pady=10)
        self.head_pressure_result = ttk.Label(tab2, text="")
        self.head_pressure_result.grid(column=3, row=5, padx=10, pady=10)
        
        # Basic heat flux calculation
        ttk.Label(tab2, text="Heat flux (W/m^2):").grid(column=0, row=6, padx=10, pady=10)
        self.heat_flux_entry = ttk.Entry(tab2)
        self.heat_flux_entry.grid(column=1, row=6, padx=10, pady=10)
        
        ttk.Label(tab2, text="Temperature difference (K):").grid(column=0, row=7, padx=10, pady=10)
        self.temp_diff_entry = ttk.Entry(tab2)
        self.temp_diff_entry.grid(column=1, row=7, padx=10, pady=10)
        
        ttk.Button(tab2, text="Calculate Heat Flux", command=self.calculate_heat_flux).grid(column=2, row=7, padx=10, pady=10)
        self.heat_flux_result = ttk.Label(tab2, text="")
        self.heat_flux_result.grid(column=3, row=7, padx=10, pady=10)

    def convert_flow_rate(self):
        try:
            flow_rate_m3s = float(self.flow_rate_entry.get())
            flow_rate_Lmin = flow_rate_m3s * 1000 * 60
            self.flow_rate_result.config(text=f"{flow_rate_Lmin:.2f} L/min")
        except ValueError:
            self.flow_rate_result.config(text="Invalid input")
    
    def convert_density(self):
        try:
            density_kg_m3 = float(self.density_entry.get())
            density_g_cm3 = density_kg_m3 / 1000
            self.density_result.config(text=f"{density_g_cm3:.3f} g/cm^3")
        except ValueError:
            self.density_result.config(text="Invalid input")
    
    def calculate_k_factor(self):
        try:
            viscosity = float(self.viscosity_entry.get())
            density = float(self.k_density_entry.get())
            k_factor = (viscosity / density) ** 0.5
            self.k_factor_result.config(text=f"{k_factor:.5f}")
        except ValueError:
            self.k_factor_result.config(text="Invalid input")
    
    def calculate_head_pressure(self):
        try:
            flow_rate = float(self.head_flow_rate_entry.get())
            density = float(self.head_density_entry.get())
            head_pressure = density * (flow_rate ** 2) / (2 * 9.81)
            self.head_pressure_result.config(text=f"{head_pressure:.2f} Pa")
        except ValueError:
            self.head_pressure_result.config(text="Invalid input")
    
    def calculate_heat_flux(self):
        try:
            heat_flux = float(self.heat_flux_entry.get())
            temp_diff = float(self.temp_diff_entry.get())
            heat_flux_result = heat_flux / temp_diff
            self.heat_flux_result.config(text=f"{heat_flux_result:.2f} W/(m^2·K)")
        except ValueError:
            self.heat_flux_result.config(text="Invalid input")
    
if __name__ == "__main__":
    root = tk.Tk()
    app = FuelPropertiesCalculator(root)
    root.mainloop()
