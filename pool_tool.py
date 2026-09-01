# pylint: disable=trailing-whitespace
# pylint: disable=line-too-long
# pylint: disable=too-many-locals
# pylint: disable=invalid-name
# pylint: disable=broad-exception-caught
# pylint: disable=missing-function-docstring
# pylint: disable=too-few-public-methods
# pylint: disable=redefined-outer-name
# pylint: disable=import-error
"""
INTELLIGENT POOL CHEMISTRY ASSISTANT
with SLAM Lifecycle Detection and Smart Recommendations
"""

import os
import sys
import traceback
import tkinter as tk
from pathlib import Path
from datetime import datetime
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from typing import Optional, Dict, Any

# Simple direct import - both files are in the same directory
from guidance_builder import GuidanceBuilder

# ==============================
# CALCULATION CONSTANTS (stay at module level - they're truly global constants)
# ==============================
CALCULATION_CONSTANTS = {
    'ACID_PH_DOSE': 120,           # ml of 31.45% HCl to drop pH by 0.1 in 10,000L
    'SODA_ASH_PH_DOSE': 100,       # g to raise pH by 0.1 in 10,000L
    'ACID_TA_DOSE': 120,           # ml of 31.45% HCl to drop TA by 10 ppm in 10,000L
    'BAKING_SODA_TA_DOSE': 180,    # g to raise TA by 10 ppm in 10,000L
    'LIQUID_CHLORINE_DOSE': 80,    # ml of 12.5% bleach → +1 ppm in 10,000L
    'CAL_HYPO_DOSE': 15.38,        # g of 65% cal-hypo to raise Cl by 1 ppm in 10,000L
    'CYA_DOSE': 10,                # g to raise CYA by 1 ppm in 10,000L
    'CALCIUM_DOSE': 11,            # g CaCl2 (100%) to raise CH by 1 ppm in 10,000L
}

# ==============================
# STALE STATE DETECTION
# ==============================
STALE_STATE_DAYS_THRESHOLD = 14  # Gap since last_seen_date that triggers a "still accurate?" prompt

# ==============================
# UNKNOWN CYA CONSTANTS
# ==============================
UNKNOWN_CYA = {
    'SAFE_SHOCK_LEVEL': 10.0,
    'SAFE_MAINTENANCE_MIN': 1.0,
    'SAFE_MAINTENANCE_MAX': 3.0,
    'WARNING': "⚠️ CYA unknown - test CYA for accurate chlorine ranges",
    'ASSUMPTION_FOR_SLAM_DETECTION': 30
}

# ==============================
# TARGET RANGES
# ==============================
TARGET_RANGES = {
    'pH': {'min': 7.2, 'max': 7.8, 'target': 7.5},
    'TA': {'min': 80, 'max': 120, 'target': 100},
    'Cl': {'min': 1, 'max': 3, 'target': 3},
    'CYA': {'min': 30, 'max': 50},
    'CH': {'min': 200, 'max': 400}
}

# ==============================
# WATER CLARITY OPTIONS
# ==============================
WATER_CLARITY_OPTIONS = [
    "crystal_clear",
    "slightly_cloudy", 
    "cloudy",
    "milky",
    "green_algae",
    "black_algae"
]

WATER_CLARITY_DESCRIPTIONS = {
    "crystal_clear": "Perfectly clear - can see bottom details clearly",
    "slightly_cloudy": "Blue with a slight white haze - can see bottom but details are fuzzy",
    "cloudy": "Can't see bottom clearly - looks like diluted milk",
    "milky": "White/milky appearance - typical after SLAM (dead algae). If you've passed the overnight chlorine loss test, switch to maintenance mode and focus on filtering.",
    "green_algae": "Green tint or visible green algae on surfaces",
    "black_algae": "Black/dark spots on walls or floor"
}

def get_clarity_display_name(clarity):
    if clarity is None:
        return "Unknown"
    
    names = {
        "crystal_clear": "Crystal Clear",
        "slightly_cloudy": "Slightly Cloudy", 
        "cloudy": "Cloudy",
        "milky": "Milky (Post-SLAM)",
        "green_algae": "Green Algae",
        "black_algae": "Black Algae"
    }
    return names.get(clarity, str(clarity).replace('_', ' ').title())

def get_clarity_internal_key(display_name):
    for clarity_item in WATER_CLARITY_OPTIONS:
        if get_clarity_display_name(clarity_item) == display_name:
            return clarity_item
    return 'crystal_clear'

# ==============================
# AppState Class
# ==============================
class AppState:
    """
    Application state management class for the Pool Chemistry Assistant.
    
    This class maintains the runtime state of the application, including configuration
    data, window references, and UI component references that need to be accessed
    across different parts of the application.
    
    Attributes:
        config (Dict[str, Any]): Dictionary containing all application configuration
            settings loaded from pool_config.txt. Includes pool volume, chemical
            percentages, water clarity, overnight test status, and previous state
            information.
        
        config_file (str): Full file path to the configuration file
            (pool_config.txt) where settings are persisted.
        
        overnight_test_frame (Optional[tk.LabelFrame]): Reference to the overnight
            test UI frame, used to control its visibility and update its content
            based on SLAM state.
        
        dilution_calculator_window (Optional[DilutionCalculatorWindow]): Reference
            to the dilution calculator window instance. Used to prevent multiple
            instances and to bring existing window to front when requested.
        
        dilution_button (Optional[tk.Button]): Reference to the dilution calculator
            button, used to manage its enabled/disabled state and visual feedback
            while opening the calculator.
        
        main_window_ready (bool): Flag indicating whether the main application
            window has completed initialization and is ready for user interaction.
            Used to prevent actions that require fully initialized UI components.
    
    Example:
        state = AppState()
        state.config['pool_volume'] = 10000
        state.config_file = "/path/to/pool_config.txt"
        state.main_window_ready = True
    """
    def __init__(self):
        self.config: Dict[str, Any] = {}
        self.config_file: str = ""
        self.overnight_test_frame: Optional[tk.LabelFrame] = None
        self.dilution_calculator_window: Optional['DilutionCalculatorWindow'] = None
        self.dilution_button: Optional[tk.Button] = None
        self.main_window_ready: bool = False

# ==============================
# ToolTip Class
# ==============================
class ToolTip:
    """Create a tooltip for a given widget."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
    
    def enter(self, _event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tooltip, text=self.text, justify='left',
                         background="#ffffe0", relief='solid', borderwidth=1,
                         font=("Arial", 10))
        label.pack()
    
    def leave(self, _event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

# ==============================
# Dilution Calculator Window Class
# ==============================
class DilutionCalculatorWindow:
    """Standalone window for calculating chlorine levels using sample dilution."""
    
    def __init__(self, parent, app_state, chlorine_entry=None):
        try:
            self.parent = parent
            self.app_state = app_state
            self.chlorine_entry = chlorine_entry
            self.is_ready = False
            self._opening_config = False

            # ADD TYPE HINTS
            self.water_volume_entry: tk.Entry
            self.drops_entry: tk.Entry
            self.ratio_frame: tk.LabelFrame
            self.recipe_text: tk.Text
            self.result_entry: tk.Entry
            self.calculate_btn: tk.Button
            self.result_label: tk.Label
            self.status_label: tk.Label
            self.config_btn: tk.Button
            self._pending_recipe: Optional[str] = None
            self._config_found: bool = False
            self._config_loaded_successfully: bool = False
            
            # Create window
            self.window = tk.Toplevel(parent)
            self.window.title("🧪 Dilution Calculator (for High FC Testing)")
            self.window.geometry("700x750")
            self.window.configure(bg="white")
            self.window.transient(parent)
            self.window.protocol("WM_DELETE_WINDOW", self.on_close)
            
            # Test kit configuration
            self.test_method = "drop"
            self.test_kit_max = 5.0
            self.test_kit_steps = [0.5, 1.0, 1.5, 2.0, 3.0]
            
            # Initialize StringVars
            self.water_volume_var = tk.StringVar(value="10")
            self.drops_var = tk.StringVar(value="5")
            self.dilution_method_var = tk.StringVar(value="1:1")
            self.auto_copy_var = tk.BooleanVar(value=True)
            self.result_var = tk.StringVar(value="")
            self.dilution_result_var = tk.StringVar(value="Actual FC: --")
           
            # Make window modal
            self.window.grab_set()
            
            # Center window
            self.center_window()
            
            # Load config and create UI
            self.load_saved_config()
            self.create_widgets()
            self.initialize_recipe()
            
            self.is_ready = True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dilution calculator:\n{str(e)}")
            if hasattr(self, 'window'):
                self.window.destroy()
    
    def center_window(self):
        """Center the window on screen."""
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'{width}x{height}+{x}+{y}')
    
    def on_close(self):
        """Handle window close event."""
        self.app_state.dilution_calculator_window = None
        self.window.destroy()
    
    def safe_configure_test_kit(self):
        """Safely open configure dialog only when window is ready."""
        if not self.is_ready:
            self.window.after(100, self.safe_configure_test_kit)
            return
        self.configure_test_kit()
    
    def create_widgets(self):
        """Create all UI widgets for the dilution calculator."""
        try:
            # Main container with scrollbar
            main_container = tk.Frame(self.window, bg="white")
            main_container.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Create scrollable frame
            inner_canvas = tk.Canvas(main_container, bg="white", highlightthickness=0)
            inner_scrollbar = tk.Scrollbar(main_container, orient="vertical", command=inner_canvas.yview)
            scrollable_frame = tk.Frame(inner_canvas, bg="white")
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: inner_canvas.configure(scrollregion=inner_canvas.bbox("all"))
            )
            
            inner_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            inner_canvas.configure(yscrollcommand=inner_scrollbar.set)
            
            inner_canvas.pack(side="left", fill="both", expand=True)
            inner_scrollbar.pack(side="right", fill="y")
            
            # Title
            title_label = tk.Label(
                scrollable_frame, 
                text="🧪 DILUTION CALCULATOR",
                font=("Arial", 14, "bold"),
                bg="white"
            )
            title_label.pack(pady=(0, 10))
            
            # Description
            desc_text = """Use this when your test kit can't measure high chlorine levels.
Example: If kit maxes at 5 ppm, use 1:4 dilution to measure up to 25 ppm."""
            tk.Label(
                scrollable_frame,
                text=desc_text,
                font=("Arial", 9),
                bg="white",
                wraplength=550,
                justify="left"
            ).pack(pady=(0, 15))
            
            # Test Kit Configuration Button
            config_button_frame = tk.Frame(scrollable_frame, bg="white")
            config_button_frame.pack(pady=(0, 15))
            
            self.config_btn = tk.Button(
                config_button_frame,
                text="⚙️ Configure Your Test Kit Range",
                bg="#FF9800",
                fg="white",
                font=("Arial", 9, "bold"),
                padx=15,
                pady=5
            )
            # Use direct binding with click prevention
            self.config_btn.bind("<Button-1>", self.on_config_button_click)
            self.config_btn.pack()
            ToolTip(self.config_btn, "Click to set your test kit's actual measurement range and steps")
            
            # Test Kit Configuration Frame
            self.create_config_frame(scrollable_frame)
            
            # Dilution Ratio Selection
            self.create_ratio_frame(scrollable_frame)
            
            # Recipe Display
            self.create_recipe_frame(scrollable_frame)
            
            # Test Input Section
            self.create_input_frame(scrollable_frame)
            
            # Result Display
            self.create_result_frame(scrollable_frame)
            
            # Quick Reference
            self.create_reference_frame(scrollable_frame)
            
            # Status Label
            status_frame = tk.Frame(scrollable_frame, bg="white")
            status_frame.pack(fill="x", pady=(10, 0))
            
            self.status_label = tk.Label(
                status_frame,
                text="✅ Configuration auto-saved | Settings auto-load on open",
                font=("Arial", 8),
                fg="green",
                bg="white"
            )
            self.status_label.pack()
            
            # Update status based on config load
            if hasattr(self, '_config_found'):
                if self._config_found and hasattr(self, '_config_loaded_successfully') and self._config_loaded_successfully:
                    self.status_label.config(text="✅ Loaded saved settings | Changes auto-save", fg="green")
                else:
                    self.status_label.config(text="📝 Using default settings | Click ⚙️ to configure your test kit", fg="blue")
            
            # Bind Enter key to calculate
            self.result_entry.bind("<Return>", lambda e: self.calculate_and_close())
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create dilution calculator UI:\n{str(e)}")

    def on_config_button_click(self, _event):
        """Handle configure button click with click prevention."""
        if self._opening_config:
            return
        self._opening_config = True
        self.config_btn.config(state="disabled", text="⏳ Opening...")
        self.window.update_idletasks()
        self.window.after(10, self._do_configure_test_kit)

    def _do_configure_test_kit(self):
        """Actually open the configuration dialog."""
        try:
            self.configure_test_kit()
        except Exception as e:
            messagebox.showerror("Error", f"Could not open configuration:\n{e}")
        finally:
            self.window.after(500, self._reset_config_button)

    def _reset_config_button(self):
        """Reset the configure button to normal state."""
        self.config_btn.config(state="normal", text="⚙️ Configure Your Test Kit Range")
        self._opening_config = False
    
    def create_config_frame(self, parent):
        """Create the test kit configuration frame."""
        config_frame = tk.LabelFrame(
            parent,
            text="Your Test Kit Configuration",
            padx=10,
            pady=10,
            bg="white"
        )
        config_frame.pack(fill="x", pady=(0, 10))
        
        # Water volume
        vol_frame = tk.Frame(config_frame, bg="white")
        vol_frame.pack(fill="x", pady=(0, 5))
        tk.Label(vol_frame, text="Normal test water (ml):", bg="white").pack(side="left", padx=(0, 10))
        self.water_volume_entry = tk.Entry(vol_frame, textvariable=self.water_volume_var, width=10)
        self.water_volume_entry.pack(side="left")
        ToolTip(self.water_volume_entry, "Volume of water your test tube holds (usually 10-25 ml)")
        
        # Drops
        drops_frame = tk.Frame(config_frame, bg="white")
        drops_frame.pack(fill="x", pady=(5, 0))
        tk.Label(drops_frame, text="Drops for normal test:", bg="white").pack(side="left", padx=(0, 10))
        self.drops_entry = tk.Entry(drops_frame, textvariable=self.drops_var, width=10)
        self.drops_entry.pack(side="left")
        ToolTip(self.drops_entry, "Number of drops your test uses (usually 5)")
        
        # Update recipe when config changes
        def update_and_save(*args):
            self.calculate_dilution_recipe(show_result=False)
            self.save_configuration()
            self.result_var.set("")
            self.dilution_result_var.set("Actual FC: --")
            if hasattr(self, 'result_label'):
                self.result_label.config(fg="blue")
        
        self.water_volume_var.trace("w", update_and_save)
        self.drops_var.trace("w", update_and_save)
    
    def create_ratio_frame(self, parent):
        """Create the dilution ratio selection frame."""
        self.ratio_frame = tk.LabelFrame(
            parent,
            text="Choose Dilution Ratio",
            padx=10,
            pady=10,
            bg="white"
        )
        self.ratio_frame.pack(fill="x", pady=(0, 10))
        self.update_dilution_options()
    
    def create_recipe_frame(self, parent):
        """Create the recipe display frame."""
        recipe_frame = tk.LabelFrame(
            parent,
            text="📝 Dilution Recipe",
            padx=10,
            pady=10,
            bg="white"
        )
        recipe_frame.pack(fill="x", pady=(0, 10))
        
        self.recipe_text = tk.Text(
            recipe_frame,
            height=10,
            font=("Courier", 9),
            wrap="word",
            bg="#f9f9f9",
            relief="flat"
        )
        self.recipe_text.pack(fill="x")
        self.recipe_text.config(state="disabled")
        
        # Apply any pending recipe
        if hasattr(self, '_pending_recipe') and self._pending_recipe is not None:
            self.recipe_text.config(state="normal")
            self.recipe_text.delete("1.0", tk.END)
            self.recipe_text.insert("1.0", self._pending_recipe)
            self.recipe_text.config(state="disabled")
            self._pending_recipe = None  # Clear after use
    
    def create_input_frame(self, parent):
        """Create the test input frame."""
        input_frame = tk.LabelFrame(
            parent,
            text="Test Diluted Sample & Enter Reading",
            padx=10,
            pady=10,
            bg="white"
        )
        input_frame.pack(fill="x", pady=(0, 10))
        
        # Reading input
        reading_frame = tk.Frame(input_frame, bg="white")
        reading_frame.pack(fill="x", pady=(0, 10))
        tk.Label(reading_frame, text="Diluted sample reading (ppm):", bg="white").pack(side="left", padx=(0, 10))
        self.result_entry = tk.Entry(reading_frame, textvariable=self.result_var, width=15)
        self.result_entry.pack(side="left", padx=(0, 10))
        
        # Calculate button
        self.calculate_btn = tk.Button(
            reading_frame,
            text="Calculate Actual FC",
            command=self.calculate_and_close,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 9, "bold")
        )
        self.calculate_btn.pack(side="left")
    
    def create_result_frame(self, parent):
        """Create the result display frame."""
        result_display_frame = tk.Frame(parent, bg="white")
        result_display_frame.pack(fill="x", pady=(0, 10))
        
        # Actual FC result
        self.dilution_result_var = tk.StringVar(value="Actual FC: --")
        self.result_label = tk.Label(
            result_display_frame,
            textvariable=self.dilution_result_var,
            font=("Arial", 11, "bold"),
            fg="blue",
            bg="white"
        )
        self.result_label.pack(side="left", padx=(0, 20))
        
        # Auto-fill checkbox
        auto_copy_check = tk.Checkbutton(
            result_display_frame,
            text="Auto-fill Chlorine field",
            variable=self.auto_copy_var,
            bg="white",
            font=("Arial", 9),
            command=self.save_configuration
        )
        auto_copy_check.pack(side="left", padx=(0, 20))
        ToolTip(auto_copy_check, "Automatically fills the Chlorine field in main window when you calculate FC")
    
    def create_reference_frame(self, parent):
        """Create the quick reference frame."""
        ref_frame = tk.LabelFrame(
            parent,
            text="🎯 Quick Reference Guide",
            padx=10,
            pady=10,
            bg="white"
        )
        ref_frame.pack(fill="x", pady=(0, 10))
        
        ref_text = f"""YOUR TEST KIT CONFIGURATION:
    • Maximum FC: {self.test_kit_max} ppm
    • Test steps: {', '.join(str(s) for s in self.test_kit_steps)}

    FLOW:
    1. Choose dilution ratio ← Recipe appears automatically
    2. Follow recipe to prepare diluted sample
    3. Test diluted sample with your kit
    4. Enter reading above → Get actual FC (window auto-closes)

    DILUTION RATIOS AVAILABLE:
    • 1:1 = For FC 0-{self.test_kit_max * 2:.1f} ppm range
    • 1:2 = For FC 0-{self.test_kit_max * 3:.1f} ppm range
    • 1:3 = For FC 0-{self.test_kit_max * 4:.1f} ppm range
    • 1:4 = For FC 0-{self.test_kit_max * 5:.1f} ppm range
    • 1:9 = For FC 0-{self.test_kit_max * 10:.1f} ppm range

    TIPS:
    • Use distilled water from pharmacy/supermarket
    • Use syringe or pipette for accuracy
    • Record reading immediately after adding drops"""
        
        tk.Label(
            ref_frame,
            text=ref_text,
            font=("Arial", 9),
            bg="white",
            justify="left",
            wraplength=550
        ).pack(anchor="w")
    
    def update_dilution_options(self):
        """Update dilution ratio options based on test kit range."""
        # Assert ratio_frame exists
        assert self.ratio_frame is not None, "Ratio frame not initialized"

        # Store current selection before clearing
        current_selection = self.dilution_method_var.get()

        # Clear existing radio buttons
        for widget in self.ratio_frame.winfo_children():
            widget.destroy()
        
        # Calculate available dilution ratios
        ratios = self.calculate_available_ratios()
        
        # Create new radio buttons
        for method, label in ratios:
            rb_frame = tk.Frame(self.ratio_frame, bg="white")
            rb_frame.pack(anchor="w", pady=2)
            
            rb = tk.Radiobutton(
                rb_frame,
                text=label,
                variable=self.dilution_method_var,
                value=method,
                bg="white",
                font=("Arial", 9),
                command=lambda m=method: [self.calculate_dilution_recipe(show_result=False), 
                                        self.save_configuration(),
                                        self.result_var.set(""),
                                        self.dilution_result_var.set("Actual FC: --"),
                                        self.result_label.config(fg="blue")]
            )
            rb.pack(side="left")
        
        # Try to restore previous selection if it's still valid
        if current_selection in [method for method, _ in ratios]:
            self.dilution_method_var.set(current_selection)
        else:
            # If previous selection not available (maybe due to test kit range change), use 1:1
            self.dilution_method_var.set("1:1")
        
        # Update recipe
        self.calculate_dilution_recipe(show_result=False)
    
    def calculate_available_ratios(self):
        """Calculate available dilution ratios based on test kit max."""
        ratios = []
        dilution_factors = [
            (1, 1, "1:1"),
            (1, 2, "1:2"),
            (1, 3, "1:3"),
            (1, 4, "1:4"),
            (1, 9, "1:9")
        ]
        
        for pool_part, water_part, method in dilution_factors:
            factor = (pool_part + water_part) / pool_part
            max_measurable = self.test_kit_max * factor
            label = f"{method} (Up to {max_measurable:.1f} ppm FC)"
            ratios.append((method, label))
        
        return ratios
    
    def configure_test_kit(self):
        """Open dialog to configure test kit specific range."""
        if not self.is_ready:
            return
        
        
        def _open_config_window():
            config_window = tk.Toplevel(self.window)
            config_window.title("Configure Your Test Kit")
            config_window.geometry("450x450")
            config_window.configure(bg="white")
            config_window.transient(self.window)
            config_window.focus_set()
            config_window.grab_current()
            
            def cancel_config():
                config_window.destroy()
                self.window.focus_set()
            
            config_window.protocol("WM_DELETE_WINDOW", cancel_config)
            
            # Center window
            config_window.update_idletasks()
            width = config_window.winfo_width()
            height = config_window.winfo_height()
            x = (config_window.winfo_screenwidth() // 2) - (width // 2)
            y = (config_window.winfo_screenheight() // 2) - (height // 2)
            config_window.geometry(f'{width}x{height}+{x}+{y}')
            
            # Title
            tk.Label(
                config_window,
                text="Configure Your Test Kit",
                font=("Arial", 14, "bold"),
                bg="white"
            ).pack(pady=(10, 5))
            
            # Description
            desc_text = "Select which test method you're using and configure its range."
            tk.Label(
                config_window,
                text=desc_text,
                font=("Arial", 9),
                bg="white",
                wraplength=400,
                justify="left"
            ).pack(pady=(0, 15))
            
            # Test method selection
            method_frame = tk.Frame(config_window, bg="white")
            method_frame.pack(pady=(0, 15))
            
            tk.Label(method_frame, text="Test method:", font=("Arial", 10, "bold"), 
                    bg="white").pack(anchor="w")
            
            test_method_var = tk.StringVar(value=self.test_method)
            
            methods_frame = tk.Frame(method_frame, bg="white")
            methods_frame.pack(fill="x", pady=(5, 0))
            
            # Test strips option
            strips_frame = tk.Frame(methods_frame, bg="white")
            strips_frame.pack(side="left", padx=(0, 20))
            tk.Radiobutton(
                strips_frame,
                text="Test Strips",
                variable=test_method_var,
                value="strips",
                bg="white",
                font=("Arial", 9)
            ).pack(anchor="w")
            tk.Label(strips_frame, text="(0-5 ppm typical)", 
                    font=("Arial", 8), fg="gray", bg="white").pack(anchor="w")
            
            # Drop test option
            drops_frame = tk.Frame(methods_frame, bg="white")
            drops_frame.pack(side="left")
            tk.Radiobutton(
                drops_frame,
                text="Drop Test (DPD/FAS-DPD)",
                variable=test_method_var,
                value="drop",
                bg="white",
                font=("Arial", 9)
            ).pack(anchor="w")
            tk.Label(drops_frame, text="(0-3 ppm typical)", 
                    font=("Arial", 8), fg="gray", bg="white").pack(anchor="w")
            
            # Max FC input
            max_frame = tk.Frame(config_window, bg="white")
            max_frame.pack(pady=(0, 10), fill="x", padx=20)
            
            tk.Label(max_frame, text="Maximum FC your kit can measure (ppm):", 
                    font=("Arial", 9),
                    bg="white").pack(anchor="w")
            
            max_var = tk.StringVar(value=str(self.test_kit_max))
            max_entry = tk.Entry(max_frame, textvariable=max_var, width=10)
            max_entry.pack(anchor="w", pady=(5, 0))
            
            # Update max based on method selection
            def update_max_from_method():
                if test_method_var.get() == "strips":
                    max_var.set("5")
                else:
                    max_var.set("3")
            
            tk.Button(
                max_frame,
                text="Set to method default",
                command=update_max_from_method,
                font=("Arial", 8)
            ).pack(anchor="w", pady=(5, 0))
            
            # Steps input
            steps_frame = tk.Frame(config_window, bg="white")
            steps_frame.pack(pady=(0, 15), fill="x", padx=20)
            
            tk.Label(steps_frame, text="Steps on your test (comma-separated):", 
                    font=("Arial", 9),
                    bg="white").pack(anchor="w")
            
            steps_text = ", ".join(str(step) for step in self.test_kit_steps)
            steps_var = tk.StringVar(value=steps_text)
            steps_entry = tk.Entry(steps_frame, textvariable=steps_var, width=40)
            steps_entry.pack(fill="x", pady=(5, 5))
            
            tk.Label(
                steps_frame,
                text="Example: 0.5, 1, 1.5, 2, 3, 5, 10",
                font=("Arial", 8),
                fg="gray",
                bg="white"
            ).pack(anchor="w")
            
            # Preset steps
            preset_frame = tk.Frame(config_window, bg="white")
            preset_frame.pack(pady=(0, 15), fill="x", padx=20)
            
            tk.Label(preset_frame, text="Quick presets:", 
                    font=("Arial", 9, "bold"),
                    bg="white").pack(anchor="w", pady=(0, 5))
            
            presets_buttons = tk.Frame(preset_frame, bg="white")
            presets_buttons.pack(fill="x")
            
            def set_preset(test_method, max_val, steps):
                test_method_var.set(test_method)
                max_var.set(str(max_val))
                steps_var.set(", ".join(str(s) for s in steps))

            tk.Button(presets_buttons, text="Strips (0-5 ppm)", 
                    command=lambda: set_preset("strips", 5.0, [0.5, 1.0, 1.5, 2.0, 3.0, 5.0]),
                    font=("Arial", 8)).pack(side="left", padx=(0, 5))

            tk.Button(presets_buttons, text="Drop Test (0-3 ppm)", 
                    command=lambda: set_preset("drop", 3.0, [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]),
                    font=("Arial", 8)).pack(side="left", padx=(0, 5))

            tk.Button(presets_buttons, text="Extended (0-10 ppm)", 
                    command=lambda: set_preset("drop", 10.0, [0.5, 1, 2, 3, 5, 7.5, 10]),  # Using drop test for extended range
                    font=("Arial", 8)).pack(side="left", padx=(0, 5))
            
            # Buttons
            button_frame = tk.Frame(config_window, bg="white")
            button_frame.pack(pady=(10, 0))
            
            def save_kit_config():
                try:
                    new_max = float(max_var.get())
                    if new_max <= 0:
                        raise ValueError("Max must be positive")
                    
                    steps_text = steps_var.get()
                    steps_list = []
                    for step in steps_text.split(','):
                        step = step.strip()
                        if step:
                            steps_list.append(float(step))
                    
                    if not steps_list:
                        raise ValueError("Enter at least one step value")
                    
                    # Save all settings
                    self.test_method = test_method_var.get()
                    self.test_kit_max = new_max
                    self.test_kit_steps = steps_list
                    self.save_configuration()
                    self.update_dilution_options()
                    
                    config_window.destroy()
                    self.window.focus_set()
                    messagebox.showinfo("Success", "Test kit configuration saved!")
                    
                except ValueError as e:
                    messagebox.showerror("Error", f"Invalid input: {str(e)}")
            
            tk.Button(
                button_frame,
                text="Save Configuration",
                command=save_kit_config,
                bg="#4CAF50",
                fg="white",
                font=("Arial", 9, "bold")
            ).pack(side="left", padx=(0, 10))
            
            tk.Button(
                button_frame,
                text="Cancel",
                command=cancel_config,
                bg="#f44336",
                fg="white",
                font=("Arial", 9)
            ).pack(side="left")
        
        self.window.after(10, _open_config_window)
    
    def calculate_dilution_recipe(self, show_result=True):
        """Calculate and display dilution recipe."""
        try:
            # Get configuration
            normal_ml = float(self.water_volume_var.get())
            if normal_ml <= 0:
                raise ValueError("Water volume must be positive")
                
            drops = float(self.drops_var.get())
            if drops <= 0:
                raise ValueError("Drops must be positive")
                
            method = self.dilution_method_var.get()
            
            # Parse dilution ratio
            try:
                pool_parts, water_parts = map(int, method.split(":"))
            except Exception:
                pool_parts, water_parts = 1, 1
            
            # Calculate amounts
            total_diluted_ml = normal_ml
            pool_ml = total_diluted_ml * (pool_parts / (pool_parts + water_parts))
            distilled_ml = total_diluted_ml * (water_parts / (pool_parts + water_parts))
            factor = (pool_parts + water_parts) / pool_parts
            diluted_drops = drops * (pool_ml / normal_ml)
            
            # Build recipe
            recipe = f"""DILUTION RECIPE for your {normal_ml} ml test tube:
    ────────────────────────────────
    1. MEASURE accurately:
    • Pool water:    {pool_ml:.1f} ml ({pool_ml:.1f} g)
    • Distilled water: {distilled_ml:.1f} ml ({distilled_ml:.1f} g)
    • Total: {total_diluted_ml:.1f} ml (fills test tube)
    
    2. MIX in clean container:
    • Add {pool_ml:.1f} ml pool water first
    • Add {distilled_ml:.1f} ml distilled water
    • Mix gently (no shaking - creates bubbles)

    3. TEST diluted sample:
    • Fill test tube to {normal_ml} ml mark
    • Add {diluted_drops:.0f} drops reagent
    • Compare color to normal chart
    
    4. IF USING THIS DILUTION:
    • Multiply reading by {factor:.1f}
    • Example: 2.0 ppm reading = {2.0 * factor:.1f} ppm actual FC
    ────────────────────────────────
    TIPS:
    • Use syringe or pipette for accuracy
    • Distilled water from pharmacy/supermarket
    • Record reading immediately after adding drops"""
            
            # Update recipe text
            if hasattr(self, 'recipe_text'):
                self.recipe_text.config(state="normal")
                self.recipe_text.delete("1.0", tk.END)
                self.recipe_text.insert("1.0", recipe)
                self.recipe_text.config(state="disabled")
            else:
                self._pending_recipe = recipe  # Store for later
            
            # Calculate FC if we have a reading
            if show_result and self.result_var.get().strip():
                try:
                    test_result = float(self.result_var.get().strip())
                    if test_result < 0:
                        raise ValueError("Reading cannot be negative")
                    
                    actual_fc = test_result * factor
                    
                    if hasattr(self, 'dilution_result_var'):
                        self.dilution_result_var.set(f"✅ Actual FC: {actual_fc:.1f} ppm")
                    if hasattr(self, 'result_label'):
                        self.result_label.config(fg="green")
                    
                    # Auto-fill chlorine field if checked
                    if self.auto_copy_var.get() and self.chlorine_entry:
                        self.chlorine_entry.delete(0, tk.END)
                        self.chlorine_entry.insert(0, f"{actual_fc:.1f}")
                    
                    self.save_configuration()
                    
                    # Show warning if FC is very high
                    if actual_fc > 30:
                        messagebox.showwarning(
                            "High FC Warning",
                            f"FC is very high: {actual_fc:.1f} ppm\n\n"
                            "Consider:\n"
                            "1. Using higher dilution (1:9 ratio)\n"
                            "2. Letting FC drift down naturally\n"
                            "3. Testing pH only when FC < 10 ppm"
                        )
                        
                except ValueError as e:
                    if hasattr(self, 'dilution_result_var'):
                        self.dilution_result_var.set(f"❌ Invalid reading: {str(e)}")
                    if hasattr(self, 'result_label'):
                        self.result_label.config(fg="red")
            
            elif not show_result:
                if hasattr(self, 'dilution_result_var'):
                    self.dilution_result_var.set("✅ Recipe ready - test and enter reading above")
                if hasattr(self, 'result_label'):
                    self.result_label.config(fg="blue")
                
        except ValueError as e:
            if hasattr(self, 'dilution_result_var'):
                self.dilution_result_var.set(f"❌ Configuration error: {str(e)}")
            if hasattr(self, 'result_label'):
                self.result_label.config(fg="red")
            if hasattr(self, 'recipe_text'):
                self.recipe_text.config(state="normal")
                self.recipe_text.delete("1.0", tk.END)
                self.recipe_text.insert("1.0", f"Error in kit configuration:\n{str(e)}\n\nCheck water volume and drops.")
                self.recipe_text.config(state="disabled")
    
    def calculate_and_close(self):
        """Calculate FC and auto-close window if successful."""
        self.calculate_dilution_recipe(show_result=True)
        
        # Save the current dilution ratio setting
        self.save_configuration()
        
        if hasattr(self, 'result_label') and self.result_label.cget("fg") == "green" and "✅" in self.dilution_result_var.get():
            self.window.after(500, self.on_close)
    
    def initialize_recipe(self):
        """Show default recipe on window open."""
        self.calculate_dilution_recipe(show_result=False)
    
    def save_configuration(self):
        """Save current calculator configuration automatically."""
        config = {
            'water_volume': self.water_volume_var.get(),
            'drops': self.drops_var.get(),
            'dilution_ratio': self.dilution_method_var.get(),
            'auto_fill': str(self.auto_copy_var.get()),
            'test_method': self.test_method,
            'test_kit_max': str(self.test_kit_max),
            'test_kit_steps': ','.join(str(step) for step in self.test_kit_steps)
        }
        
        exe_dir = self.get_exe_dir()
        config_file = os.path.join(exe_dir, "dilution_config.txt")
        
        try:
            with open(config_file, "w", encoding="utf-8") as f:
                for k, v in config.items():
                    f.write(f"{k}={v}\n")
            if hasattr(self, 'status_label'):
                self.status_label.config(text="✅ Configuration auto-saved", fg="green")
        except Exception:
            if hasattr(self, 'status_label'):
                self.status_label.config(text="⚠️ Could not save configuration", fg="orange")
    
    def load_saved_config(self):
        """Load saved calculator configuration automatically on window open."""
        exe_dir = self.get_exe_dir()
        config_file = os.path.join(exe_dir, "dilution_config.txt")
        
        self._config_found = os.path.exists(config_file)
        
        if not self._config_found:
            return
        
        try:
            config = {}
            with open(config_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if '=' in line:
                        k, v = line.split('=', 1)
                        config[k.strip()] = v.strip()
            
            if 'water_volume' in config:
                self.water_volume_var.set(config['water_volume'])
            if 'drops' in config:
                self.drops_var.set(config['drops'])
            if 'dilution_ratio' in config:
                self.dilution_method_var.set(config['dilution_ratio'])
            if 'auto_fill' in config:
                self.auto_copy_var.set(config['auto_fill'].lower() == 'true')
            if 'test_method' in config:
                self.test_method = config['test_method']
            
            if 'test_kit_max' in config:
                self.test_kit_max = float(config['test_kit_max'])
            if 'test_kit_steps' in config:
                steps_text = config['test_kit_steps']
                self.test_kit_steps = [float(step.strip()) for step in steps_text.split(',') if step.strip()]
            
            self._config_loaded_successfully = True
            
        except Exception as e:
            self._config_loaded_successfully = False
    
    def get_exe_dir(self):
        """Get directory of executable or script."""
        try:
            if getattr(sys, 'frozen', False):
                return os.path.dirname(sys.executable)
            return os.path.dirname(os.path.abspath(__file__))
        except Exception:
            return os.path.dirname(os.path.abspath(__file__))

# ==============================
# Main Application Class
# ==============================
class PoolChemistryApp:
    """
    Main application class for the Intelligent Pool Chemistry Assistant.
    
    This application provides intelligent pool water chemistry analysis with
    SLAM (Shock Level And Maintain) lifecycle detection and smart recommendations.
    
    Key Features:
        • SLAM Lifecycle Detection: Automatically identifies pre-SLAM, during-SLAM,
          post-SLAM, and post-SLAM final stages based on water clarity, chlorine levels,
          CYA, and overnight test results.
        
        • Intelligent State Tracking: Remembers previous session states
          (water clarity, SLAM mode) and detects suspicious transitions like
          moving from algae → milky water without reporting overnight test results.
        
        • Context-Aware Recommendations: Provides tailored advice based on where
          you are in the SLAM process - from initial algae outbreak through final
          filtering stage.
        
        • Overnight Test Integration: Tracks overnight FC loss test status
          (not_tested/passed/failed) and adjusts recommendations accordingly.
        
        • Smart Questioning: When detecting state transitions that don't add up
          (e.g., algae → milky without overnight test), asks intelligent questions
          to update the pool's story.
        
        • Persistent Configuration: Saves all settings including pool volume,
          chemical percentages, water clarity, overnight test status, and previous
          session states for continuity between sessions.
        
        • Dilution Calculator: Built-in tool for testing high chlorine levels
          (>10 ppm) when standard test kits max out.
        
        • Calculation Engine: Comprehensive chemistry calculations for pH,
          alkalinity, chlorine, CYA, and calcium hardness with proper dosing
          based on pool volume and chemical concentrations.
    
    Attributes:
        root (tk.Tk): The main tkinter window.
        app_state (AppState): Runtime application state including config and
            UI component references.
        global_config (Dict): Configuration dictionary loaded from pool_config.txt.
        global_config_file (str): Path to the configuration file.
        
        UI Components:
            entry_volume (tk.Entry): Pool volume input
            entry_cal_hypo (tk.Entry): Cal-Hypo percentage input
            entry_hcl (tk.Entry): HCl percentage input
            entry_bleach (tk.Entry): Bleach percentage input
            entry_pump_flow (tk.Entry): Pump flow rate input
            entry_pH (tk.Entry): pH test result input
            entry_chlorine (tk.Entry): Chlorine test result input
            entry_TA (tk.Entry): Total Alkalinity test result input
            entry_cya (tk.Entry): Cyanuric Acid test result input
            entry_calcium (tk.Entry): Calcium Hardness test result input
            clarity_var (tk.StringVar): Water clarity selection
            slam_mode_var (tk.BooleanVar): SLAM mode active flag
            overnight_test_var (tk.StringVar): Overnight test status
        
        State Tracking:
            _opening_calculator (bool): Flag to prevent multiple calculator instances
    
    Methods:
        check_initial_state_transition(): Checks for state transitions at startup
        detect_state_transition(): Compares previous vs current state for suspicious patterns
        ask_about_overnight_test(): Prompts user when transition detected
        calculate(): Main calculation entry point
        adjust_pool(): Core analysis engine generating recommendations
        load_config()/save_config(): Configuration persistence
        create_widgets(): UI construction
        on_clarity_change()/on_slam_mode_toggle(): Event handlers with transition detection
    """
    
    def __init__(self, root):
        """Initialize the main application."""
        self.root = root
        self.root.title("Intelligent Pool Chemistry Assistant")
        self.root.geometry("550x800")
        
        # Add flag to prevent multiple clicks
        self._opening_calculator = False
        
        # Initialize app state
        self.app_state = AppState()
        self.app_state.main_window_ready = False

        # ADD TYPE HINTS
        self.entry_volume: tk.Entry
        self.entry_cal_hypo: tk.Entry
        self.entry_hcl: tk.Entry
        self.entry_bleach: tk.Entry
        self.entry_pump_flow: tk.Entry
        self.entry_pH: tk.Entry
        self.entry_chlorine: tk.Entry
        self.entry_TA: tk.Entry
        self.entry_cya: tk.Entry
        self.entry_calcium: tk.Entry
        self.clarity_var: tk.StringVar
        self.clarity_combo: ttk.Combobox
        self.clarity_desc_label: tk.Label
        self.slam_mode_var: tk.BooleanVar
        self.slam_status_label: tk.Label
        self.overnight_test_var: tk.StringVar
        self.dilution_btn: tk.Button
        
        # Load configuration
        self.load_config()
        
        # Create UI
        self.create_widgets()
        
        # Check initial state SAFELY after UI is ready
        # Using after() to ensure event loop has processed everything
        self.root.after(100, self.safe_initial_transition_check)

    def safe_initial_transition_check(self):
        """Safely check initial state transitions after UI is ready."""
        if not self.app_state.main_window_ready:
            self.root.after(100, self.safe_initial_transition_check)
            return
        self.check_initial_state_transition()

    def set_main_window_ready(self):
        """Set main window as ready and enable buttons."""
        self.root.update_idletasks()
        self.app_state.main_window_ready = True
        
        # Enable dilution calculator button
        if self.dilution_btn:
            self.dilution_btn.config(state="normal")
    
    def create_widgets(self):
        """Create all UI widgets."""
        # Main scrollable frame
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill="both", expand=True)
        
        canvas = tk.Canvas(main_frame)
        scrollbar = tk.Scrollbar(main_frame, command=canvas.yview)
        scrollable = tk.Frame(canvas)
        
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        def on_config(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        scrollable.bind("<Configure>", on_config)
        
        def on_mousewheel(event):
            canvas.yview_scroll(int(-event.delta/120), "units")
        canvas.bind("<MouseWheel>", on_mousewheel)
        
        # Create all sections
        self.create_pool_setup_frame(scrollable)
        self.create_measurements_frame(scrollable)
        self.create_description_label(scrollable)
        self.create_buttons()
        self.create_status_bar()
        
        # Initialize descriptions
        self.update_clarity_desc()
        self.update_slam_status()
        
        # Sets main window to ready
        self.set_main_window_ready()
    
    def create_pool_setup_frame(self, parent):
        """Create the pool setup configuration frame."""
        cf = tk.LabelFrame(parent, text="Pool Setup", padx=10, pady=10)
        cf.pack(padx=10, pady=10, fill="x")
        
        # Volume
        tk.Label(cf, text="Volume (L):").pack(anchor="w")
        self.entry_volume = tk.Entry(cf)
        self.entry_volume.insert(0, self.app_state.config['pool_volume'])
        self.entry_volume.pack(fill="x")
        ToolTip(self.entry_volume, "Typical: 1,000–200,000 L")
                
        # HCl %
        tk.Label(cf, text="HCl (%):").pack(anchor="w")
        self.entry_hcl = tk.Entry(cf)
        self.entry_hcl.insert(0, f"{self.app_state.config['hcl_percent']:g}")
        self.entry_hcl.pack(fill="x")
        ToolTip(self.entry_hcl, "Typical: 10–35%")
        
        # Bleach %
        tk.Label(cf, text="Bleach (%):").pack(anchor="w")
        self.entry_bleach = tk.Entry(cf)
        self.entry_bleach.insert(0, f"{self.app_state.config['bleach_percent']:g}")
        self.entry_bleach.pack(fill="x")
        ToolTip(self.entry_bleach, "Typical: 5–15%")
        
        # Cal-Hypo %
        tk.Label(cf, text="Cal-Hypo (%):").pack(anchor="w")
        self.entry_cal_hypo = tk.Entry(cf)
        self.entry_cal_hypo.insert(0, f"{self.app_state.config['cal_hypo_percent']:g}")
        self.entry_cal_hypo.pack(fill="x")
        ToolTip(self.entry_cal_hypo, "Calcium Hypochlorite percentage (65% = 650g/kg, 73% = 730g/kg)")

        # Pump Flow
        tk.Label(cf, text="Pump Flow (L/h - optional):").pack(anchor="w")
        self.entry_pump_flow = tk.Entry(cf)
        pump_value = self.app_state.config.get('pump_flow_rate')
        if pump_value is not None and pump_value != 0:
            self.entry_pump_flow.insert(0, str(pump_value))
        self.entry_pump_flow.pack(fill="x")
        ToolTip(self.entry_pump_flow, "Improves wait time accuracy")
        
        # Water Clarity
        tk.Label(cf, text="Water Clarity:").pack(anchor="w", pady=(10, 0))
        self.clarity_var = tk.StringVar()
        
        clarity_display_options = []
        for clarity_key in WATER_CLARITY_OPTIONS:
            disp_text = get_clarity_display_name(clarity_key)
            clarity_display_options.append(disp_text)
        
        self.clarity_combo = ttk.Combobox(cf, textvariable=self.clarity_var, 
                                        values=clarity_display_options,
                                        state="readonly", width=25)
        self.clarity_combo.pack(fill="x")
        
        initial_clarity = self.app_state.config.get('water_clarity', 'crystal_clear')
        initial_display = get_clarity_display_name(initial_clarity)
        self.clarity_combo.set(initial_display)
        
        self.clarity_desc_label = tk.Label(cf, text="", fg="gray", font=("Arial", 9), 
                                        wraplength=400, justify="left")
        self.clarity_desc_label.pack(anchor="w", pady=(5, 0))
        
        # SLAM Mode Checkbox - initialize from saved config
        saved_slam_mode = self.app_state.config.get('previous_slam_mode', False)
        self.slam_mode_var = tk.BooleanVar(value=saved_slam_mode)
        
        slam_checkbox = tk.Checkbutton(
            cf, 
            text="🔧 ACTIVE SLAM MODE",
            variable=self.slam_mode_var,
            font=("Arial", 9, "bold"),
            fg="red",
            bg="#FFF0F0",
            command=self.on_slam_mode_toggle
        )
        slam_checkbox.pack(anchor="w", pady=(10, 0))
        ToolTip(slam_checkbox, "Check this when actively performing SLAM process. pH readings are inaccurate when FC > 10 ppm.")
        
        # SLAM status label with separators
        separator_top = tk.Frame(cf, height=1, bg="gray", relief="sunken", borderwidth=1)
        separator_top.pack(fill="x", pady=(5, 2))

        self.slam_status_label = tk.Label(
            cf, 
            text="✅ Normal mode: All parameters matter", 
            font=("Arial", 9, "bold"),
            relief="ridge",
            borderwidth=2,
            padx=5,
            pady=3
        )
        self.slam_status_label.pack(fill="x", pady=2)

        separator_bottom = tk.Frame(cf, height=1, bg="gray", relief="sunken", borderwidth=1)
        separator_bottom.pack(fill="x", pady=(2, 5))
        
        # Overnight Test Frame
        self.create_overnight_test_frame(cf)
        
        # Dilution Calculator Button
        self.create_dilution_button(cf)
        
        # Separator
        tk.Frame(cf, height=1, bg="gray").pack(fill="x", pady=(5, 0))
        
        # Bind events
        self.clarity_combo.bind("<<ComboboxSelected>>", self.on_clarity_change)
        self.slam_mode_var.trace("w", lambda *args: self.update_slam_status())

    
    def create_overnight_test_frame(self, parent):
        """Create the overnight test frame."""
        # Load saved value from config
        saved_value = self.app_state.config.get('overnight_test', 'not_tested')
        self.overnight_test_var = tk.StringVar(value=saved_value)
        self.app_state.overnight_test_frame = tk.LabelFrame(parent, text="Overnight FC Loss Test", padx=10, pady=5)
        
        # Set default styling (will be overridden by update_slam_status when needed)
        self.app_state.overnight_test_frame.config(
            bg="#F0F0F0",
            relief="groove",
            borderwidth=1
        )
        
        # Radio buttons with their own styling
        not_tested_rb = tk.Radiobutton(
            self.app_state.overnight_test_frame, 
            text="❓ Not tested (default)",
            variable=self.overnight_test_var,
            value="not_tested",
            font=("Arial", 9),
            fg="black", 
            bg="#F0F0F0",
            activebackground="#F0F0F0",
            selectcolor="#F0F0F0"
        )
        not_tested_rb.pack(anchor="w")
        
        passed_rb = tk.Radiobutton(
            self.app_state.overnight_test_frame, 
            text="✅ PASSED (FC loss ≤ 1 ppm)",
            variable=self.overnight_test_var,
            value="passed",
            font=("Arial", 9, "bold"),
            fg="green",
            bg="#F0F0F0",
            activebackground="#F0F0F0",
            selectcolor="#F0F0F0"
        )
        passed_rb.pack(anchor="w")
        
        failed_rb = tk.Radiobutton(
            self.app_state.overnight_test_frame, 
            text="❌ FAILED (FC loss > 1 ppm)",
            variable=self.overnight_test_var,
            value="failed",
            font=("Arial", 9),
            fg="red",
            bg="#F0F0F0",
            activebackground="#F0F0F0",
            selectcolor="#F0F0F0"
        )
        failed_rb.pack(anchor="w")
        
        # Description
        tk.Label(
            self.app_state.overnight_test_frame, 
            text="Definitive indicator: if passed, algae is dead (switch to filtration).",
            font=("Arial", 8),
            fg="gray",
            bg="#F0F0F0",
            wraplength=400,
            justify="left"
        ).pack(anchor="w", pady=(5, 0))
        
        # Bind to update app_state on change (but NOT save)
        self.overnight_test_var.trace("w", self.on_overnight_test_change)
        
        # Initially hide it
        self.app_state.overnight_test_frame.pack_forget()

    def on_overnight_test_change(self, *args):
        """Update app state when overnight test changes, but DON'T auto-save."""
        new_value = self.overnight_test_var.get()
        self.app_state.config['overnight_test'] = new_value
        # NO SAVE HERE - user must click Calculate to save

    def create_dilution_button(self, parent):
        """Create the dilution calculator button."""
        dilution_button_frame = tk.Frame(parent)
        dilution_button_frame.pack(fill="x", pady=(10, 5))
        
        self.dilution_btn = tk.Button(
            dilution_button_frame,
            text="🧪 Open Dilution Calculator",
            bg="#9C27B0",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=20,
            pady=5
        )
        
        # Use direct binding instead of command=
        self.dilution_btn.bind("<Button-1>", self.on_dilution_button_click)
        self.dilution_btn.pack()
        self.app_state.dilution_button = self.dilution_btn
        ToolTip(self.dilution_btn, "For testing high chlorine levels (above 10 ppm) with standard test kits")

    def on_dilution_button_click(self, _event=None):
        """Handle dilution button click directly."""
        if self._opening_calculator:
            return
        self._opening_calculator = True
        if self.dilution_btn:
            self.dilution_btn.config(state="disabled", text="⏳ Opening...")
        self.root.update_idletasks()
        self.root.after(10, self._do_open_dilution_calculator)

    def _do_open_dilution_calculator(self):
        try:
            if self.app_state.dilution_calculator_window and \
               self.app_state.dilution_calculator_window.window.winfo_exists():
                self.app_state.dilution_calculator_window.window.lift()
                self.app_state.dilution_calculator_window.window.focus_force()
            else:
                self.app_state.dilution_calculator_window = DilutionCalculatorWindow(
                    self.root, self.app_state, self.entry_chlorine)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open dilution calculator:\n{str(e)}")
        finally:
            self.root.after(500, self._reset_dilution_button)

    def _reset_dilution_button(self):
        """Reset the dilution button to normal state."""
        self.dilution_btn.config(state="normal", text="🧪 Open Dilution Calculator")
        self._opening_calculator = False
    
    def create_measurements_frame(self, parent):
        """Create the test results input frame."""
        mf = tk.LabelFrame(parent, text="Test Results", padx=10, pady=10)
        mf.pack(padx=10, pady=10, fill="x")
        
        # pH
        tk.Label(mf, text="pH (7.2–7.8 ideal):").pack(anchor="w")
        self.entry_pH = tk.Entry(mf)
        self.entry_pH.pack(fill="x", pady=(0, 8))
        ToolTip(self.entry_pH, "pH")
        
        # Chlorine
        tk.Label(mf, text="Chlorine (0–3 ppm typical):").pack(anchor="w")
        self.entry_chlorine = tk.Entry(mf)
        self.entry_chlorine.pack(fill="x", pady=(0, 8))
        ToolTip(self.entry_chlorine, "Chlorine")
        
        # TA
        tk.Label(mf, text="TA (80–120 ppm):").pack(anchor="w")
        self.entry_TA = tk.Entry(mf)
        self.entry_TA.pack(fill="x", pady=(0, 8))
        ToolTip(self.entry_TA, "Total Alkalinity")
        
        # CYA
        tk.Label(mf, text="CYA (30–50 ppm):").pack(anchor="w")
        self.entry_cya = tk.Entry(mf)
        self.entry_cya.pack(fill="x", pady=(0, 8))
        ToolTip(self.entry_cya, "Cyanuric Acid")
        
        # Calcium
        tk.Label(mf, text="Calcium (200–400 ppm):").pack(anchor="w")
        self.entry_calcium = tk.Entry(mf)
        self.entry_calcium.pack(fill="x", pady=(0, 8))
        ToolTip(self.entry_calcium, "Calcium Hardness")
    
    def create_description_label(self, parent):
        """Create the description label."""
        desc = (
            "🎯 INTELLIGENT SLAM DETECTION:\n"
            "• Automatically detects pre-SLAM, during-SLAM, and post-SLAM conditions\n"
            "• Provides context-aware recommendations\n"
            "• Complete chemistry analysis for all parameters\n"
            "• Water clarity selection enables smart algae treatment guidance"
        )
        desc_label = tk.Label(parent, text=desc, wraplength=500, justify="left", 
                              font=("Arial", 10), bg="#f0f8ff", relief="ridge", padx=10, pady=10)
        desc_label.pack(pady=10, fill="x", padx=10)
    
    def create_buttons(self):
        """Create the bottom buttons."""
        btns = tk.Frame(self.root)
        btns.pack(pady=15)
        
        tk.Button(btns, text="Calculate", command=self.calculate, bg="#4CAF50", fg="white", 
                  font=("Arial", 10, "bold")).pack(side="left", padx=5)
        tk.Button(btns, text="History", command=self.view_history, bg="#2196F3", fg="white").pack(side="left", padx=5)
        tk.Button(btns, text="Reset", command=self.reset_defaults, bg="#f44336", fg="white").pack(side="left", padx=5)
    
    def create_status_bar(self):
        """Create the status bar."""
        status = tk.Label(self.root, text="Ready", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status.pack(side=tk.BOTTOM, fill=tk.X)
    
    # ==============================
    # Event Handlers
    # ==============================
    
    def on_clarity_change(self, event=None):
        """Handle clarity change - update description and check for transitions."""
        self.update_clarity_desc(event)
        self.update_slam_status()
        
        # Update config in memory only
        water_clarity_display = self.clarity_var.get()
        water_clarity = get_clarity_internal_key(water_clarity_display)
        self.app_state.config['water_clarity'] = water_clarity
        
        # If algae is selected and overnight test is "passed", reset it
        if water_clarity in ["green_algae", "black_algae"] and self.overnight_test_var:
            if self.overnight_test_var.get() == "passed":
                old_value = self.overnight_test_var.get()
                self.overnight_test_var.set("not_tested")
                self.app_state.config['overnight_test'] = "not_tested"
        
        # Check if this change creates a transition
        transition = self.detect_state_transition()
        if transition['transition_detected']:
            self.ask_about_overnight_test(transition)
    
    def update_clarity_desc(self, _event=None):
        """Update the clarity description based on selection."""
        selected_display = self.clarity_var.get()
        internal_key = None
        for clarity_type in WATER_CLARITY_OPTIONS:
            if get_clarity_display_name(clarity_type) == selected_display:
                internal_key = clarity_type
                break
        
        if internal_key and self.clarity_desc_label:
            self.clarity_desc_label.config(text=WATER_CLARITY_DESCRIPTIONS[internal_key])
        elif self.clarity_desc_label:
            self.clarity_desc_label.config(text="")
    
    def update_slam_status(self):
        """Update SLAM status and control overnight test visibility."""
        if self.slam_mode_var.get():
            # SLAM mode ACTIVE - with boxed style
            if self.slam_status_label:
                self.slam_status_label.config(
                    text="⚠️ SLAM MODE ACTIVE: Testing chlorine frequently, ignoring pH accuracy\nOnly chlorine and CYA matter",
                    bg="#FFEBEE",
                    fg="#D32F2F",
                    relief="ridge",
                    font=("Arial", 9, "bold"),
                    justify="center"
                )
            
            # Show overnight test frame with SLAM styling
            if self.app_state.overnight_test_frame is not None:
                self.app_state.overnight_test_frame.pack(fill="x", pady=(5, 0))
                self.app_state.overnight_test_frame.config(
                    bg="#FFEBEE",
                    relief="ridge",
                    borderwidth=2
                )
                
                # Update radio button colors based on their values
                for child in self.app_state.overnight_test_frame.winfo_children():
                    if isinstance(child, tk.Radiobutton):
                        if child.cget("value") == "passed":
                            child.config(fg="green", bg="#FFEBEE")
                        elif child.cget("value") == "failed":
                            child.config(fg="red", bg="#FFEBEE")
                        else:
                            child.config(fg="black", bg="#FFEBEE")
                    elif isinstance(child, tk.Label):
                        child.config(bg="#FFEBEE", fg="gray")
        
        else:
            # Normal mode - with boxed style
            if self.slam_status_label:
                self.slam_status_label.config(
                    text="✅ Normal mode: All parameters matter",
                    bg="#E8F5E9",
                    fg="#2E7D32",
                    relief="ridge",
                    font=("Arial", 9, "bold"),
                    justify="center"
                )
            
            # Hide overnight test frame when SLAM mode is off
            if self.app_state.overnight_test_frame is not None:
                self.app_state.overnight_test_frame.pack_forget()    
    

    def on_slam_mode_toggle(self):
        """Handle SLAM mode toggle with user guidance."""
        if self.slam_mode_var.get():
            response = messagebox.askyesno(
                "Enable SLAM Mode?",
                "🔧 SLAM MODE ACTIVATION\n\n"
                "You're about to enable SLAM mode. This will:\n"
                "1. Show the Overnight Test section\n"
                "2. Focus recommendations on chlorine/CYA only\n"
                "3. Assume pH readings are inaccurate (FC > 10 ppm)\n\n"
                "⚠️ Only enable during active SLAM process!\n\n"
                "Enable SLAM mode?"
            )
            if not response:
                self.slam_mode_var.set(False)
                return
            
            if self.app_state.overnight_test_frame is not None:
                self.app_state.overnight_test_frame.config(bg="#FFF0F0", relief="solid", borderwidth=2)
            
            messagebox.showinfo(
                "SLAM Mode Active",
                "✅ SLAM MODE ENABLED\n\n"
                "Important reminders:\n"
                "• Test chlorine every 2-4 hours\n"
                "• Use Dilution Calculator for readings > 10 ppm\n"
                "• Brush pool daily\n"
                "• Run pump 24/7\n"
                "• Complete the Overnight Test to know when algae is dead"
            )
        else:
            # When disabling SLAM mode, reset overnight test to not_tested
            if self.overnight_test_var:
                old_value = self.overnight_test_var.get()
                self.overnight_test_var.set("not_tested")
                self.app_state.config['overnight_test'] = "not_tested"
            
            if self.overnight_test_var and self.overnight_test_var.get() == "passed":
                messagebox.showinfo(
                    "Overnight Test Passed",
                    "✅ Great job! Overnight test passed means algae is dead.\n\n"
                    "Now focus on:\n"
                    "1. Filtering out dead algae\n"
                    "2. Maintaining normal chlorine levels\n"
                    "3. Testing all parameters normally"
                )
            elif self.overnight_test_var and self.overnight_test_var.get() == "failed":
                messagebox.showwarning(
                    "Overnight Test Failed",
                    "❌ Overnight test failed - algae still present.\n\n"
                    "Continue SLAM until:\n"
                    "1. Water is no longer green\n"
                    "2. FC loss ≤ 1 ppm overnight\n"
                    "3. Water is clear or milky (dead algae)"
                )
        
        # Update config in memory
        self.app_state.config['previous_slam_mode'] = self.slam_mode_var.get()
        
        self.update_slam_status()
        
        # Check if this change creates a transition
        transition = self.detect_state_transition()
        if transition['transition_detected']:
            self.ask_about_overnight_test(transition)
    
    def detect_state_transition(self):
        """Compare previous state vs current state to detect suspicious patterns."""
        
        # Get previous state from config
        prev_clarity = self.app_state.config.get('previous_water_clarity', 'crystal_clear')
        prev_slam = self.app_state.config.get('previous_slam_mode', False)
        
        # Get current state
        curr_clarity = get_clarity_internal_key(self.clarity_var.get())
        curr_slam = self.slam_mode_var.get()
        overnight = self.overnight_test_var.get()
        
        # Only trigger if overnight test is still "not_tested"
        if overnight != 'not_tested':
            return {'transition_detected': False}
        
        # Only trigger if something ACTUALLY changed (prevents startup spam)
        if prev_clarity == curr_clarity and prev_slam == curr_slam:
            return {'transition_detected': False}
        
        # SCENARIO 1: Previous session had algae + SLAM ON → Now milky + SLAM OFF
        if (prev_clarity in ['green_algae', 'black_algae'] and 
            prev_slam is True and
            curr_clarity == 'milky' and
            curr_slam is False):
            
            return {
                'transition_detected': True,
                'scenario': 'algae_to_milky_without_test',
                'message': (
                    "Last time, you were fighting algae with SLAM mode ON.\n"
                    "Now the water is milky (dead algae) and SLAM mode is OFF.\n\n"
                    "But you never told me if you passed the overnight FC loss test.\n\n"
                    "Did you PASS the overnight test (FC loss ≤ 1 ppm)?"
                ),
                'yes_action': 'set_passed',
                'no_action': 'set_failed_and_slam',
                'cancel_action': 'no_change'
            }
        
        # SCENARIO 2: Previously milky (post-SLAM), now algae again (regrowth)
        if (prev_clarity == 'milky' and
            curr_clarity in ['green_algae', 'black_algae']):
            
            return {
                'transition_detected': True,
                'scenario': 'regrowth',
                'message': (
                    "Your water was previously milky (dead algae), but now algae is back.\n"
                    "This usually means the overnight test FAILED or you stopped SLAM too early.\n\n"
                    "Did you complete and PASS the overnight FC loss test?"
                ),
                'yes_action': 'investigate_further',
                'no_action': 'restart_slam',
                'cancel_action': 'no_change'
            }
        
        # SCENARIO 3: SLAM was ON, now OFF, but water still has issues
        if (prev_slam is True and
            curr_slam is False and
            curr_clarity in ['cloudy', 'green_algae', 'black_algae']):
            
            return {
                'transition_detected': True,
                'scenario': 'slam_stopped_early',
                'message': (
                    f"You've turned SLAM mode OFF, but your water still shows:\n"
                    f"• {get_clarity_display_name(curr_clarity)}\n\n"
                    "Did you actually COMPLETE the SLAM process?\n"
                    "Have you passed the overnight FC loss test?"
                ),
                'yes_action': 'continue_maintenance',
                'no_action': 'reenable_slam',
                'cancel_action': 'no_change'
            }
        
        # SCENARIO 4: Algae detected with SLAM off (unified algae detection)
        if (curr_clarity in ['green_algae', 'black_algae'] and
            curr_slam is False):
            
            return {
                'transition_detected': True,
                'scenario': 'algae_detected',
                'message': (
                    "I see you have algae in your pool.\n"
                    "SLAM mode is not enabled.\n\n"
                    "Would you like me to guide you through the SLAM process?"
                ),
                'yes_action': 'show_preslam_guidance',
                'no_action': 'no_action',
                'cancel_action': 'no_change'
            }
        
        return {'transition_detected': False}

    def ask_about_overnight_test(self, transition_info):
        """Ask user about state transitions with appropriate questions."""
        
        scenario = transition_info.get('scenario', '')
        message = transition_info['message']
        
        # SCENARIO 1: Algae → milky without test
        if scenario == 'algae_to_milky_without_test':
            response = messagebox.askyesnocancel(
                "Overnight Test Needed",
                message + "\n\n"
                "Yes → I passed, algae is dead\n"
                "No → I failed, still need SLAM\n"
                "Cancel → I haven't done the test yet"
            )
            
            if response is True:  # Yes - they passed
                self.overnight_test_var.set("passed")
                self.slam_mode_var.set(False)
                messagebox.showinfo(
                    "Great!",
                    "✅ Overnight test PASSED! Algae is dead.\n\n"
                    "Focus on filtration to clear the dead algae."
                )
                self._save_current_state()
                
            elif response is False:  # No - they failed
                self.overnight_test_var.set("failed")
                self.slam_mode_var.set(True)
                messagebox.showinfo(
                    "Continue SLAM",
                    "❌ Overnight test FAILED. Algae is still alive.\n\n"
                    "I've re-enabled SLAM mode. Keep fighting!"
                )
                self._save_current_state()
            
            else:  # Cancel
                pass  # Keep current state
        
        # SCENARIO 2: Milky → Algae (regrowth)
        elif scenario == 'regrowth':
            response = messagebox.askyesnocancel(
                "Algae Regrowth",
                message + "\n\n"
                "Yes → I passed the test but algae returned\n"
                "No → I didn't pass the test\n"
                "Cancel → Not sure yet"
            )
            
            if response is True:  # Yes - passed test but algae returned
                messagebox.showwarning(
                    "Investigate Further",
                    "⚠️ If you truly passed the overnight test:\n\n"
                    "Check for:\n"
                    "• Low CYA (not protecting chlorine)\n"
                    "• High phosphates\n"
                    "• Hidden algae in plumbing\n"
                    "• Insufficient filtration"
                )
                # NO SAVE - just providing info
                
            elif response is False:  # No - didn't pass test
                self.overnight_test_var.set("failed")
                self.slam_mode_var.set(True)
                messagebox.showinfo(
                    "Restart SLAM",
                    "❌ Restarting SLAM process.\n\n"
                    "Keep SLAM active until you pass the overnight test."
                )
                self._save_current_state()
                
            else:  # Cancel
                pass  # Keep current state
        
        # SCENARIO 3: SLAM stopped early
        elif scenario == 'slam_stopped_early':
            response = messagebox.askyesnocancel(
                "SLAM Stopped Early?",
                message + "\n\n"
                "Yes → I completed SLAM, continue with maintenance\n"
                "No → I stopped too early, re-enable SLAM\n"
                "Cancel → Keep current settings"
            )
            
            if response is True:  # Yes - completed SLAM
                messagebox.showinfo(
                    "Maintenance Mode",
                    "✅ Continuing with maintenance mode.\n\n"
                    "Focus on:\n"
                    "• Regular chlorine levels\n"
                    "• Filtration\n"
                    "• Weekly testing"
                )
                self._save_current_state()  # Save current state (SLAM off)
                
            elif response is False:  # No - stopped too early
                self.slam_mode_var.set(True)
                messagebox.showinfo(
                    "SLAM Reactivated",
                    "⚡ I've re-enabled SLAM mode.\n\n"
                    "Keep SLAM active until:\n"
                    "1. Water turns milky\n"
                    "2. You pass overnight test\n"
                    "3. THEN switch to maintenance"
                )
                self._save_current_state()
                
            else:  # Cancel
                pass  # Keep current settings
        
        # SCENARIO 4: Unified algae detection (any algae with SLAM off)
        elif scenario == 'algae_detected':
            response = messagebox.askyesnocancel(
                "Algae Detected",
                message + "\n\n"
                "Yes → Guide me through the SLAM process\n"
                "No → I'll handle it myself\n"
                "Cancel → Not now"
            )
            
            if response is True:  # Yes - want guidance
                messagebox.showinfo(
                    "SLAM Guidance",
                    "📋 Here's your SLAM plan:\n\n"
                    "1. Test and adjust pH to 7.2-7.8\n"
                    "2. Test CYA to determine shock level\n"
                    "3. Calculate initial chlorine dose\n"
                    "4. Enable SLAM mode and begin\n\n"
                    "Run Calculate for specific numbers!"
                )
                # NO SAVE - just providing info
                
            elif response is False:  # No - handle it themselves
                # Optional: Could set a flag or just proceed
                pass
                
            else:  # Cancel
                pass  # Keep current state
        
        # Offer to recalculate if they have values entered
        if any([self.entry_pH.get().strip(), self.entry_chlorine.get().strip(), 
                self.entry_TA.get().strip(), self.entry_cya.get().strip(), 
                self.entry_calcium.get().strip()]):
            if messagebox.askyesno("Recalculate?", "Update recommendations with this new information?"):
                self.calculate()
                
    def check_initial_state_transition(self):
        """Check for state transitions when app starts."""
        if self.check_stale_state():
            return
        transition = self.detect_state_transition()
        if transition['transition_detected']:
            self.ask_about_overnight_test(transition)

    def check_stale_state(self):
        """
        Warn if the saved water clarity/SLAM state is old enough to likely be stale
        (e.g. the pool was drained over winter and refilled since the last session).
        Returns True if the prompt fired, so the caller can skip the normal
        transition check for this run.
        """
        curr_clarity = get_clarity_internal_key(self.clarity_var.get())
        if curr_clarity == 'crystal_clear':
            return False

        last_seen = self.app_state.config.get('last_seen_date')
        if not last_seen:
            return False

        try:
            last_seen_dt = datetime.strptime(last_seen, '%Y-%m-%d')
        except ValueError:
            return False

        days_gap = (datetime.now() - last_seen_dt).days
        if days_gap < STALE_STATE_DAYS_THRESHOLD:
            return False

        reset = messagebox.askyesno(
            "Long Gap Since Last Session",
            f"It's been {days_gap} days since your last recorded session ({last_seen}).\n\n"
            f"Your saved water clarity is still \"{get_clarity_display_name(curr_clarity)}\" from back then.\n\n"
            "If conditions changed since -- the pool was drained, refilled with fresh water, "
            "or sat unused over winter -- that saved state no longer applies.\n\n"
            "Reset water clarity, SLAM mode, and overnight test to fresh defaults now?"
        )

        if reset:
            self.clarity_combo.set(get_clarity_display_name('crystal_clear'))
            self.app_state.config['water_clarity'] = 'crystal_clear'
            self.slam_mode_var.set(False)
            self.app_state.config['previous_slam_mode'] = False
            if self.overnight_test_var:
                self.overnight_test_var.set('not_tested')
            self.app_state.config['overnight_test'] = 'not_tested'
            self.update_clarity_desc()
            self.update_slam_status()
            self._save_current_state()
            messagebox.showinfo(
                "Reset to Fresh",
                "✅ Water clarity, SLAM mode, and overnight test reset to defaults.\n\n"
                "Enter your current readings and Calculate as normal."
            )

        return True
    
    def safe_open_dilution_calculator(self):
        """Open dilution calculator only when main window is ready."""
        if not self.app_state.main_window_ready:
            messagebox.showinfo("Please Wait", "Application is still initializing. Please try again in a moment.")
            return
        
        # Disable button and show loading state
        if self.dilution_btn:
            self.dilution_btn.config(
                state="disabled", 
                text="⏳ Opening...", 
                bg="#4A0072",
                fg="white"
            )
        self.root.update_idletasks()
        
        # Open the calculator
        self.open_dilution_calculator()
        
        # Re-enable button after a short delay
        self.root.after(500, lambda: self.dilution_btn.config(
            state="normal", 
            text="🧪 Open Dilution Calculator",
            bg="#9C27B0",
            fg="white"
        ) if self.dilution_btn else None)
    
    def open_dilution_calculator(self):
        """Open dilution calculator window."""
        
        if self.app_state.dilution_calculator_window is not None:
            try:
                if self.app_state.dilution_calculator_window.window.winfo_exists():
                    self.app_state.dilution_calculator_window.window.lift()
                    self.app_state.dilution_calculator_window.window.focus_force()
                    
                    if self.dilution_btn:
                        self.dilution_btn.config(state="normal", text="🧪 Open Dilution Calculator", bg="#9C27B0", fg="white")
                    return
            except Exception:
                self.app_state.dilution_calculator_window = None
        
        try:
            self.app_state.dilution_calculator_window = DilutionCalculatorWindow(
                self.root, 
                self.app_state,
                self.entry_chlorine
            )
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Could not open dilution calculator:\n{str(e)}")
            if self.dilution_btn:
                self.dilution_btn.config(state="normal", text="🧪 Open Dilution Calculator", bg="#9C27B0", fg="white")
    
    def reset_defaults(self):
        if messagebox.askyesno("Reset", "Reset all inputs to defaults?"):
            # Handle pump flow separately first (might be None)
            pump_default = self.app_state.config.get('pump_flow_rate')
            pump_display = str(pump_default) if pump_default is not None else ""
            
            # Dictionary of widget:default_value pairs (as strings for display)
            defaults = {
                self.entry_volume: str(self.app_state.config.get('pool_volume', "7250")),
                self.entry_hcl: str(self.app_state.config.get('hcl_percent', "31.45")),
                self.entry_bleach: str(self.app_state.config.get('bleach_percent', "12.5")),
                self.entry_cal_hypo: "65",
                self.entry_pump_flow: pump_display,
            }
            
            # Reset all the entry widgets
            for widget, default_value in defaults.items():
                if widget:
                    widget.delete(0, tk.END)
                    if default_value:
                        widget.insert(0, default_value)
            
            # Reset measurement entries (clear them all)
            for widget in [self.entry_pH, self.entry_TA, self.entry_chlorine, 
                        self.entry_cya, self.entry_calcium]:
                if widget:
                    widget.delete(0, tk.END)

            # Reset combobox
            if self.clarity_combo:
                self.clarity_combo.set(get_clarity_display_name("crystal_clear"))
            
            # Reset boolean/string vars
            if self.slam_mode_var:
                self.slam_mode_var.set(False)
            
            if self.overnight_test_var:
                self.overnight_test_var.set("not_tested")
            
            # Update config and SAVE
            self.app_state.config.update({
                'water_clarity': 'crystal_clear',
                'overnight_test': 'not_tested',
                'previous_slam_mode': False
            })
            save_config(self.app_state.config, self.app_state.config_file, self)
            
            self.update_clarity_desc()
            self.update_slam_status()


    # ==============================
    # CHEMISTRY CALCULATION METHODS
    # ==============================
    # All of these methods contain the EXACT same logic as your original functions
    # They've just been moved inside the class and now reference self.
    
    def has_slam_recommendation(self, actions):
        """Check if actions already contain a SLAM recommendation header."""
        slam_headers = [
            "🔍 PRE-SLAM ASSESSMENT",
            "⚡ ACTIVE SLAM IN PROGRESS", 
            "🔄 POST-SLAM RECOVERY",
            "🔄 POST-SLAM FINAL STAGE"
        ]
        for action in actions:
            if any(header in action for header in slam_headers):
                return True
        return False
    
    def get_waiting_time(self, pool_volume_liters, pump_flow_rate, treatment_type):
        """Calculate waiting time for treatments."""
        if treatment_type == "aeration":
            return (12, 24, "Aeration is slow")
        
        # Handle None or zero pump flow rate
        if pump_flow_rate is None or pump_flow_rate <= 0:
            if treatment_type in ["acid", "base"]:
                return (2, 4, "Standard mixing (no pump rate provided)")
            elif treatment_type == "alkalinity":
                return (4, 6, "Baking soda dissolves slowly (no pump rate provided)")
            else:
                return (2, 4, "Standard mixing (no pump rate provided)")
        
        # Safe to calculate turnover now
        turnover_time = pool_volume_liters / pump_flow_rate
        min_turnovers = 1.0
        max_turnovers = 1.5
        if treatment_type == "alkalinity":
            min_turnovers, max_turnovers = 1.5, 2.0
        
        min_hours = max(1, turnover_time * min_turnovers)
        max_hours = max(2, turnover_time * max_turnovers)
        return (min_hours, max_hours, f"Turnover: {turnover_time:.1f}h (based on {pump_flow_rate:.0f} L/h)")
    
    def ta_from_soda_ash(self, grams, pool_volume_liters):
        """Calculate TA increase from soda ash."""
        return (grams / 100) * 14 * (10000 / pool_volume_liters)
    
    def get_high_dose_note(self, acid_ml, V, pump):
        """Check for high dose and provide split instructions."""
        if acid_ml > V * 0.015:
            turnover = V / pump if pump else None
            split_hours = max(2, turnover * 1.5) if turnover else 6
            half_ml = acid_ml / 2
            return f"\n   HIGH DOSE: Add {half_ml:.0f} ml now, {half_ml:.0f} ml after {split_hours:.1f} hrs"
        return ""
    
    # ==============================
    # STATUS HELPER METHODS
    # ==============================
    
    def get_ph_status(self, pH, context='normal'):
        """Get formatted pH status."""
        if pH is None:
            return "Not tested"
        
        if pH < TARGET_RANGES['pH']['min']:
            return f"Low ({pH:.2f})"
        elif pH > TARGET_RANGES['pH']['max']:
            return f"High ({pH:.2f})"
        else:
            if context == 'post_slam':
                if pH < 7.4:
                    return f"Slightly low ({pH:.2f}) - ideal for aeration"
                elif pH > 7.6:
                    return f"Slightly high ({pH:.2f}) - monitor closely"
                else:
                    return f"Ideal ({pH:.2f}) - perfect for post-slam"
            return f"Good ({pH:.2f})"
    
    def get_ta_status(self, alkalinity):
        """Get formatted TA status."""
        if alkalinity is None:
            return "Not tested"
        
        if alkalinity < TARGET_RANGES['TA']['min']:
            return f"Low ({alkalinity} ppm)"
        elif alkalinity > TARGET_RANGES['TA']['max']:
            return f"High ({alkalinity} ppm)"
        else:
            return f"Good ({alkalinity} ppm)"
    
    def get_chlorine_status(self, chlorine, cya, context='normal'):
        """Get formatted chlorine status with CYA awareness."""
        if chlorine is None:
            return "Not tested"
        
        if cya is None:
            if chlorine < UNKNOWN_CYA['SAFE_MAINTENANCE_MIN']:
                return f"Low ({chlorine:.1f} ppm) - CYA unknown"
            elif chlorine > UNKNOWN_CYA['SAFE_MAINTENANCE_MAX']:
                return f"High ({chlorine:.1f} ppm) - CYA unknown"
            elif chlorine >= UNKNOWN_CYA['SAFE_MAINTENANCE_MIN'] and chlorine <= UNKNOWN_CYA['SAFE_MAINTENANCE_MAX']:
                return f"Good ({chlorine:.1f} ppm) - CYA unknown"
            else:
                return f"({chlorine:.1f} ppm) - CYA unknown"
        
        if cya == 0:
            shock_level = 10.0
            maintenance_min = 1.0
        elif cya < 30:
            shock_level = 10.0
            maintenance_min = cya * 0.075
        else:
            shock_level = cya * 0.4
            maintenance_min = cya * 0.075
        
        if context == 'during_slam':
            if chlorine >= shock_level * 0.9:
                return f"At shock level ({chlorine:.1f} ppm)"
            else:
                return f"Below shock level ({chlorine:.1f} ppm)"
        
        if context == 'post_slam':
            if chlorine >= maintenance_min and chlorine <= (cya * 0.15):
                return f"Ideal for recovery ({chlorine:.1f} ppm)"
            elif chlorine > (cya * 0.15) and chlorine < shock_level:
                return f"Appropriate ({chlorine:.1f} ppm)"
        
        if chlorine < maintenance_min:
            return f"Low for CYA {cya} ({chlorine:.1f} ppm)"
        elif chlorine > shock_level * 1.5:
            return f"Very high ({chlorine:.1f} ppm)"
        elif chlorine > TARGET_RANGES['Cl']['max'] and chlorine <= shock_level:
            return f"Elevated but safe ({chlorine:.1f} ppm)"
        elif chlorine >= maintenance_min and chlorine <= (cya * 0.15):
            return f"Ideal for CYA {cya} ({chlorine:.1f} ppm)"
        
        return f"Good ({chlorine:.1f} ppm)"
    
    def get_cya_status(self, cya, context='normal'):
        """Get formatted CYA status."""
        if cya is None:
            return "Not tested"
        
        if cya < TARGET_RANGES['CYA']['min']:
            if context == 'post_slam':
                if cya == 0:
                    shock_display = 10.0
                    note = " (no CYA - 10 ppm)"
                elif cya < 30:
                    shock_display = 10.0
                    note = " (low CYA - 10 ppm)"
                else:
                    shock_display = cya * 0.4
                    note = ""
                
                return f"Low ({cya} ppm) → Shock level only {shock_display:.1f} ppm{note}"
            return f"Low ({cya} ppm)"
        elif cya > TARGET_RANGES['CYA']['max']:
            return f"High ({cya} ppm)"
        else:
            return f"Good ({cya} ppm)"
    
    def get_calcium_status(self, calcium):
        """Get formatted calcium status."""
        if calcium is None:
            return "Not tested"
        
        if calcium < TARGET_RANGES['CH']['min']:
            return f"Low ({calcium} ppm)"
        elif calcium > TARGET_RANGES['CH']['max']:
            return f"High ({calcium} ppm)"
        else:
            return f"Good ({calcium} ppm)"
        
    def _save_current_state(self):
        """Helper method to save current UI state to config file."""
        # Update config with current UI values
        self.app_state.config.update({
            'overnight_test': self.overnight_test_var.get(),
            'previous_slam_mode': self.slam_mode_var.get(),
            'previous_water_clarity': get_clarity_internal_key(self.clarity_var.get()),
            'water_clarity': get_clarity_internal_key(self.clarity_var.get())
        })

    def calculate_safe_doses(self, chemical_type, amount_needed, V, config, context=None):
        """
        Centralized safety calculator for chemical doses.
        
        Args:
            chemical_type: 'acid', 'cal_hypo', 'liquid_chlorine', 'soda_ash', 'baking_soda'
            amount_needed: The calculated amount (ml for liquids, g for solids)
            V: Pool volume in liters
            config: Configuration dict with percentages, pump flow, etc.
            context: Optional context like 'slam', 'maintenance', 'pre_slam', 'post_slam' for tailored messaging
        
        Returns:
            dict with safe_amount, split_instructions, warnings
        """
        result = {
            'safe_amount': amount_needed,
            'split_instructions': '',
            'warnings': [],
            'single_dose_possible': True
        }
        
        pump = config.get('pump_flow_rate')
        is_slam = context in ['during_slam', 'pre_slam'] if context else False
        is_post_slam = context == 'post_slam' if context else False
        
        if chemical_type == 'acid':
            # Acid safety: Use the same threshold as get_high_dose_note
            max_safe_acid = V * 0.015  # 1.5% of pool volume (108.75ml for 7250L)
            
            if amount_needed > max_safe_acid:
                # Calculate wait time between doses
                turnover = V / pump if pump else None
                wait_hours = max(2, turnover * 0.5) if turnover else 2
                
                # Calculate how many safe doses this represents
                safe_dose_count = int(amount_needed / max_safe_acid) + 1
                
                # Progressive dosing strategy based on number of doses needed
                if safe_dose_count == 2:
                    # 2 doses: 50% now, 50% later
                    first_dose = amount_needed * 0.5
                    second_dose = amount_needed * 0.5
                    
                    result['safe_amount'] = first_dose
                    result['split_instructions'] = (
                        f"⚠️ Split into 2 doses:\n"
                        f"   • Add {first_dose:.0f} ml now\n"
                        f"   • Wait {wait_hours:.1f} hours, then add {second_dose:.0f} ml"
                    )
                    result['warnings'].append("Large acid dose - split into 2 applications")
                    
                elif safe_dose_count == 3:
                    # 3 doses: 50% now, 25% later, 25% final
                    first_dose = amount_needed * 0.5
                    second_dose = amount_needed * 0.25
                    third_dose = amount_needed * 0.25
                    
                    result['safe_amount'] = first_dose
                    result['split_instructions'] = (
                        f"⚠️ Progressive dosing (3 doses):\n"
                        f"   • Add {first_dose:.0f} ml now\n"
                        f"   • Wait {wait_hours:.1f} hours, retest pH\n"
                        f"   • Add {second_dose:.0f} ml\n"
                        f"   • Wait another {wait_hours:.1f} hours\n"
                        f"   • Add final {third_dose:.0f} ml if still needed"
                    )
                    result['warnings'].append("Large acid dose - progressive 3-dose schedule")
                    
                elif safe_dose_count == 4:
                    # 4 doses: 40% now, 20% x 3 later
                    first_dose = amount_needed * 0.4
                    remaining = amount_needed * 0.6
                    subsequent = remaining / 3  # 20% each
                    
                    result['safe_amount'] = first_dose
                    result['split_instructions'] = (
                        f"⚠️ Progressive dosing (4 doses):\n"
                        f"   • Add {first_dose:.0f} ml now\n"
                        f"   • Wait {wait_hours:.1f} hours, retest pH\n"
                        f"   • Add {subsequent:.0f} ml\n"
                        f"   • Wait {wait_hours:.1f} hours, retest\n"
                        f"   • Add {subsequent:.0f} ml\n"
                        f"   • Wait {wait_hours:.1f} hours\n"
                        f"   • Add final {subsequent:.0f} ml if needed"
                    )
                    result['warnings'].append("Very large acid dose - 4-dose progressive schedule")
                    
                else:  # 5+ doses - use equal splitting with progressive principle
                    # For 5+, use 80% of safe limit as base dose
                    base_dose = max_safe_acid * 0.8
                    num_doses = int(amount_needed / base_dose) + 1
                    first_dose = base_dose
                    remaining = amount_needed - first_dose
                    subsequent = remaining / (num_doses - 1)
                    
                    instruction_lines = [
                        f"⚠️ EXTREME DOSE - {num_doses}-dose progressive schedule:",
                        f"   • Add {first_dose:.0f} ml now"
                    ]
                    
                    for i in range(1, num_doses):
                        instruction_lines.append(f"   • Wait {wait_hours:.1f} hours, retest pH")
                        if i == num_doses - 1:
                            instruction_lines.append(f"   • Add final {subsequent:.0f} ml if needed")
                        else:
                            instruction_lines.append(f"   • Add {subsequent:.0f} ml")
                    
                    result['safe_amount'] = first_dose
                    result['split_instructions'] = "\n".join(instruction_lines)
                    result['warnings'].append(f"Extremely large acid dose - {num_doses} doses recommended")
                
                # Context-specific warnings
                if is_slam:
                    result['warnings'].append("During SLAM, you can add doses more frequently (every 2 hours) to maintain shock level")
                
                result['single_dose_possible'] = False
        
        elif chemical_type == 'cal_hypo':
            # Cal-Hypo safety: concentration-based warnings
            cal_hypo_percent = config.get('cal_hypo_percent', 65.0)
            concentration_g_per_1000L = (amount_needed / V) * 1000
            
            result['concentration'] = concentration_g_per_1000L
            
            if concentration_g_per_1000L > 50:
                # Severe concentration - safety warning but DON'T force split during SLAM
                split_count = max(2, int(concentration_g_per_1000L / 25))
                split_amount = amount_needed / split_count
                
                # Store the split info but don't force it during SLAM
                result['safe_amount'] = amount_needed  # Keep original for SLAM
                result['split_instructions'] = (
                    f"⚠️ VERY HIGH CONCENTRATION ({concentration_g_per_1000L:.1f} g/1000L) of {cal_hypo_percent}% cal-hypo:\n"
                    f"   • If you choose to split: {split_count} doses of {split_amount:.0f}g each, 2 hours apart\n"
                    f"   • Pre-dissolve each dose in bucket of pool water"
                )
                
                # Context-specific warnings
                if is_slam:
                    result['warnings'].append(
                        f"⚠️ HIGH CONCENTRATION ({concentration_g_per_1000L:.1f} g/1000L) of {cal_hypo_percent}% cal-hypo - "
                        f"Add all at once for SLAM effectiveness, but pre-dissolve in multiple buckets and broadcast widely"
                    )
                    result['single_dose_possible'] = True  # Allow single dose during SLAM
                else:
                    result['warnings'].append(
                        f"Cal-Hypo concentration very high ({concentration_g_per_1000L:.1f} g/1000L) at {cal_hypo_percent}% - "
                        f"strongly recommend splitting into {split_count} doses"
                    )
                    result['single_dose_possible'] = False  # Force split in normal mode
                    
            elif concentration_g_per_1000L > 25:
                # Moderate concentration - pre-dissolve warning
                result['split_instructions'] = (
                    f"⚠️ Pre-dissolve {amount_needed:.0f}g of {cal_hypo_percent}% cal-hypo in bucket before adding"
                )
                
                if is_slam:
                    result['warnings'].append(
                        f"Pre-dissolve {cal_hypo_percent}% cal-hypo in bucket - add all at once for SLAM effectiveness"
                    )
                else:
                    result['warnings'].append(
                        f"Moderate Cal-Hypo concentration ({concentration_g_per_1000L:.1f} g/1000L) at {cal_hypo_percent}% - pre-dissolve required"
                    )
        
        elif chemical_type == 'liquid_chlorine':
            # Liquid chlorine safety: volume-based warnings with concentration awareness
            bleach_percent = config.get('bleach_percent', 12.5)
            
            # Adjust threshold based on concentration
            volume_threshold = V * 0.015  # 1.5% of pool volume
            if bleach_percent < 10:  # Weak bleach needs larger volume
                volume_threshold = V * 0.02  # 2% threshold
            elif bleach_percent > 15:  # Strong bleach - be more conservative
                volume_threshold = V * 0.012  # 1.2% threshold
            
            if amount_needed > volume_threshold:
                turnover = V / pump if pump else None
                wait_hours = max(2, turnover * 1.5) if turnover else 6
                split_amount = amount_needed / 2
                
                # Store split info but don't force during SLAM
                result['safe_amount'] = amount_needed if is_slam else split_amount  # Keep original for SLAM
                result['split_instructions'] = (
                    f"⚠️ LARGE VOLUME ({amount_needed:.0f} ml of {bleach_percent}% bleach):\n"
                    f"   • If you choose to split: Add {split_amount:.0f} ml now, {split_amount:.0f} ml after {wait_hours:.1f} hours"
                )
                
                # Context-specific warnings
                if is_slam:
                    result['warnings'].append(
                        "⚠️ LARGE VOLUME - Add all at once for SLAM effectiveness, but pour slowly around the pool perimeter"
                    )
                    result['single_dose_possible'] = True  # Allow single dose during SLAM
                else:
                    result['warnings'].append("Large liquid chlorine volume - split into 2 doses for safety")
                    result['single_dose_possible'] = False  # Force split in normal mode
            
            # Add concentration-specific warnings (these remain the same)
            if bleach_percent > 15:
                result['warnings'].append(
                    f"⚠️ Using high-strength {bleach_percent}% bleach - handle with care, avoid splashing"
                )
            elif bleach_percent < 8:
                result['warnings'].append(
                    f"⚠️ Low-strength {bleach_percent}% bleach - you'll need larger volumes than standard 12.5%"
                )
        
        elif chemical_type == 'soda_ash':
            # Soda ash safety: impact on TA
            ta_impact = (amount_needed / 100) * 14 * (10000 / V)
            result['ta_impact'] = ta_impact
            
            if ta_impact > 20:
                warning = f"⚠️ This soda ash dose will raise TA by ~{ta_impact:.0f} ppm"
                
                # Context-specific advice
                if is_post_slam:
                    warning += "\n   • During post-SLAM, consider aeration instead to avoid TA spikes"
                elif is_slam:
                    warning += "\n   • During SLAM, focus on chlorine - address pH after SLAM if possible"
                
                result['warnings'].append(warning)
        
        elif chemical_type == 'baking_soda':
            # Baking soda is generally safe, but note the amount
            if amount_needed > 5000:  # 5kg is a lot
                warning = f"⚠️ Large baking soda dose ({amount_needed:.0f}g)"
                
                if is_slam:
                    warning += "\n   • During SLAM, add slowly over 1-2 hours to avoid cloudiness"
                else:
                    warning += "\n   • Add slowly over 30 minutes, with pump running"
                
                result['warnings'].append(warning)
        
        return result
    
    # ==============================
    # SLAM LIFE CYCLE DETECTION
    # ==============================
    
    def detect_slam_context(self, pH, chlorine, cya, water_clarity="crystal_clear", overnight_test="not_tested", is_slam_mode=False):
        """
        Intelligently detect where we are in the SLAM lifecycle.
        Returns: 'pre_slam', 'during_slam', 'post_slam', 'post_slam_final', 'normal'
        """
        # If SLAM mode is OFF, ignore overnight test results
        if not is_slam_mode:
            overnight_test = "not_tested"  # Treat as not tested when SLAM mode is off
        
        # ALWAYS check for algae FIRST - this overrides everything
        if water_clarity in ["green_algae", "black_algae"]:
            return 'pre_slam'
        
        # Only then check overnight test (which will be "not_tested" if SLAM mode is off)
        if overnight_test == "passed":
            return 'post_slam_final'
        
        # Handle milky water (dead algae)
        if water_clarity == "milky":
            if chlorine is not None:
                # Calculate safe maintenance ceiling - handle None CYA case here
                if cya is None:
                    maintenance_max = UNKNOWN_CYA['SAFE_MAINTENANCE_MAX']
                elif cya == 0:
                    maintenance_max = 3.0
                else:
                    maintenance_max = cya * 0.15

                # If chlorine is near maintenance levels, we're in post-SLAM
                if chlorine <= maintenance_max * 1.5:
                    if overnight_test == "failed":
                        return 'during_slam'
                    else:
                        return 'post_slam'
                else:
                    # Chlorine still high - still in SLAM
                    return 'during_slam'
            else:
                # Milky but no chlorine reading - can't determine accurately
                return 'post_slam'  # Best guess

        # From here, water_clarity is crystal_clear, slightly_cloudy, or cloudy
        # (algae and milky clarities always return above)
        temp_cya = cya if cya is not None else UNKNOWN_CYA['ASSUMPTION_FOR_SLAM_DETECTION']

        if chlorine is None or temp_cya is None:
            return 'normal'

        if temp_cya == 0:
            shock_level = 10.0
            maintenance_min = 1.0
            maintenance_max = 3.0
        elif temp_cya < 30:
            shock_level = 10.0
            maintenance_min = temp_cya * 0.075
            maintenance_max = temp_cya * 0.15
        else:
            shock_level = temp_cya * 0.4
            maintenance_min = temp_cya * 0.075
            maintenance_max = temp_cya * 0.15

        if chlorine >= shock_level * 0.9:
            return 'during_slam'

        if chlorine > maintenance_max * 2 and chlorine < shock_level:
            if pH is not None and pH < 7.4:
                return 'post_slam'

        risk_factors = 0
        if chlorine is not None and chlorine < maintenance_min:
            risk_factors += 1
        if water_clarity in ["slightly_cloudy", "cloudy"]:
            risk_factors += 1
        if pH is not None and pH > 7.8:
            risk_factors += 1
        if cya is not None and cya < 30:
            risk_factors += 1
        
        if risk_factors >= 2:
            return 'pre_slam'
        
        return 'normal'
    
    # ==============================
    # COMPREHENSIVE SLAM GUIDANCE
    # ==============================
    
    def get_slam_guidance_structured(self, chlorine, cya, pH, water_clarity="crystal_clear", config=None, slam_context=None):
        """
        Returns structured SLAM guidance with raw data for the builder to format.
        
        Returns:
            dict: {
                'context': str,
                'is_manual_slam': bool,
                'is_cya_unknown': bool,
                'shock_level': float,
                'maintenance_min': float,
                'maintenance_max': float,
                'sections': {
                    'assessment': list[str],
                    'doses': Optional[Dict],  # Complex dose dict from calculate_chlorine_addition_options
                    'maintenance': list[str],
                    'pump_guidance': list[str],
                    'milestone': list[str],
                    'protocol': list[str],
                    'warnings': list[str]
                },
                'issues': list[str]
            }
        """
        # Determine context if not provided - ensure it's always a boolean
        is_manual_slam = False
        if config:
            is_manual_slam = config.get('is_slam_mode', False)
            # Ensure it's a boolean
            if not isinstance(is_manual_slam, bool):
                is_manual_slam = bool(is_manual_slam)
        
        if slam_context is None:
            if is_manual_slam:
                slam_context = 'during_slam'
            else:
                slam_context = self.detect_slam_context(pH, chlorine, cya, water_clarity, is_slam_mode=is_manual_slam)
        
        # Calculate target levels
        is_cya_unknown = cya is None
        calculation_cya = 0 if is_cya_unknown else cya
        
        if calculation_cya == 0:
            shock_level = UNKNOWN_CYA['SAFE_SHOCK_LEVEL']
            maintenance_min = UNKNOWN_CYA['SAFE_MAINTENANCE_MIN']
            maintenance_max = UNKNOWN_CYA['SAFE_MAINTENANCE_MAX']
        elif calculation_cya < 30:
            shock_level = UNKNOWN_CYA['SAFE_SHOCK_LEVEL']
            maintenance_min = calculation_cya * 0.075
            maintenance_max = calculation_cya * 0.15
        else:
            shock_level = calculation_cya * 0.4
            maintenance_min = calculation_cya * 0.075
            maintenance_max = calculation_cya * 0.15
        
        # Initialize result structure
        result = {
            'context': slam_context,
            'is_manual_slam': is_manual_slam,
            'is_cya_unknown': is_cya_unknown,
            'shock_level': shock_level,
            'maintenance_min': maintenance_min,
            'maintenance_max': maintenance_max,
            'sections': {
                'assessment': [],
                'doses': None,
                'maintenance': [],
                'pump_guidance': [],
                'milestone': [],
                'protocol': [],
                'warnings': []
            },
            'issues': []
        }
        
        current_fc = chlorine if chlorine is not None else 0
        
        # ===== PRE-SLAM SECTION =====
        if slam_context == 'pre_slam':
            result['sections']['assessment'].append("🔍 PRE-SLAM ASSESSMENT")
            
            # CYA unknown warnings
            if is_cya_unknown:
                if water_clarity in ["green_algae", "black_algae"]:
                    result['sections']['warnings'].append("⚠️ **CRITICAL**: CYA unknown with algae present")
                    result['sections']['warnings'].append("Using safe shock level of 10 ppm")
                    result['sections']['warnings'].append("**TEST CYA ASAP** - required for proper SLAM procedure")
                elif water_clarity in ["milky", "cloudy", "slightly_cloudy"]:
                    result['sections']['warnings'].append("⚠️ CYA unknown with cloudy water")
                    result['sections']['warnings'].append("Using safe shock level of 10 ppm")
                    result['sections']['warnings'].append("Test CYA for accurate chlorine maintenance")
            
            # Detect issues
            if chlorine is not None and chlorine < 1.0:
                result['issues'].append(f"Chlorine very low ({chlorine:.1f} ppm)")
            if water_clarity in ["slightly_cloudy", "cloudy"]:
                result['issues'].append(f"Water clarity: {water_clarity.replace('_', ' ')}")
            if water_clarity in ["green_algae", "black_algae"]:
                result['issues'].append(f"Visible algae: {water_clarity.replace('_', ' ')}")
            if pH is not None and pH > 7.8:
                result['issues'].append(f"pH too high ({pH:.2f})")
            if cya is not None and cya < 30:
                result['issues'].append(f"CYA too low ({cya} ppm) - shock level limited to 10 ppm")
            elif cya is None:
                result['issues'].append("CYA unknown - using safe shock level of 10 ppm")
            
            if result['issues']:
                result['sections']['assessment'].append(f"   Issues detected: {', '.join(result['issues'])}")
                
                fc_needed = max(0, shock_level - current_fc)
                
                # CYA info
                if cya is None:
                    result['sections']['assessment'].append(f"   CYA: Unknown → Required safe shock level: {shock_level:.1f} ppm")
                elif cya == 0:
                    result['sections']['assessment'].append(f"   CYA: {cya} ppm → Required shock level: {shock_level:.1f} ppm (no CYA)")
                else:
                    result['sections']['assessment'].append(f"   CYA: {cya} ppm → Required shock level: {shock_level:.1f} ppm")
                
                # CYA testing reminder
                if is_cya_unknown:
                    result['sections']['assessment'].append("")
                    result['sections']['assessment'].append("🔬 **CYA TESTING REQUIRED BEFORE FULL SLAM:**")
                    result['sections']['assessment'].append("   1. Test CYA ASAP using proper test kit")
                    result['sections']['assessment'].append("   2. If CYA > 30 ppm, adjust shock level to CYA × 0.4")
                    result['sections']['assessment'].append("   3. If CYA > 100 ppm, partial drain may be needed")
                
                # Calculate doses
                if config and fc_needed > 0:
                    V = config['pool_volume_liters']
                    bleach = config['bleach_percent']
                    cal_hypo_percent = config.get('cal_hypo_percent', 65.0)
                    
                    # Get raw dose data (not formatted strings)
                    dose_data = self.calculate_chlorine_addition_options(
                        current_fc=current_fc,
                        target_fc=shock_level,
                        volume_liters=V,
                        bleach_percent=bleach,
                        cal_hypo_percent=cal_hypo_percent,
                        is_slam=True,
                        cya=cya,
                        split_threshold_ppm=10.0,
                        split_interval_hours=4
                    )
                    
                    # Store the COMPLEX dict in sections['doses']
                    result['sections']['doses'] = dose_data
                
                # SLAM process steps
                result['sections']['protocol'].append("📋 SLAM PROCESS:")
                result['sections']['protocol'].append("   1. Test and adjust pH to 7.2-7.8 FIRST (7.2 is ideal for SLAM effectiveness)")
                result['sections']['protocol'].append(f"   2. Add chlorine to reach {shock_level:.1f} ppm")
                result['sections']['protocol'].append("   3. Test FC every 2-4 hours, maintain shock level:")
                result['sections']['protocol'].append("      • Expect 2-4 ppm FC drop per 2-4 hour test initially")
                result['sections']['protocol'].append("      • Drops will decrease as algae dies (good sign!)")
                result['sections']['protocol'].append(f"      • Each test: top up to {shock_level:.1f} ppm if below")
                result['sections']['protocol'].append("   4. Brush walls/floors daily")
                result['sections']['protocol'].append("   5. Run pump 24/7")
                result['sections']['protocol'].append("   6. Test overnight FC loss (key milestone):")
                result['sections']['protocol'].append("      • Test FC at night, then morning")
                result['sections']['protocol'].append("      • If FC loss ≤ 1.0 ppm: ✅ Algae dead!")
                result['sections']['protocol'].append("      • Switch to maintenance chlorine")
                result['sections']['protocol'].append("      • Water will clear in 3-7 days with filtration")
            else:
                result['sections']['assessment'].append("   No immediate SLAM required")
                if is_cya_unknown:
                    result['sections']['warnings'].append(UNKNOWN_CYA['WARNING'])
                    result['sections']['assessment'].append(f"   Safe maintenance range: {UNKNOWN_CYA['SAFE_MAINTENANCE_MIN']}-{UNKNOWN_CYA['SAFE_MAINTENANCE_MAX']} ppm")
                elif cya == 0:
                    result['sections']['assessment'].append("   Maintenance range: 1-3 ppm (no CYA)")
                else:
                    result['sections']['assessment'].append(f"   Maintenance range: {cya * 0.075:.1f}-{cya * 0.15:.1f} ppm")
        
        # ===== DURING SLAM SECTION =====
        elif slam_context == 'during_slam':
            if is_manual_slam:
                result['sections']['maintenance'].append("⚡ **USER-MANUAL SLAM MODE ACTIVE**")
            else:
                result['sections']['maintenance'].append("⚡ ACTIVE SLAM IN PROGRESS")
            
            if chlorine is not None:
                current_percent = (chlorine / shock_level * 100) if shock_level > 0 else 0
                result['sections']['maintenance'].append(f"   Current FC: {chlorine:.1f} ppm ({current_percent:.0f}% of target {shock_level:.1f} ppm)")
                
                # Calculate dose if below shock level
                if chlorine < shock_level * 0.95:
                    fc_needed = shock_level - chlorine
                    if config:
                        V = config['pool_volume_liters']
                        bleach = config['bleach_percent']
                        cal_hypo_percent = config.get('cal_hypo_percent', 65.0)
                        
                        # Calculate the dose using your centralized function
                        dose_data = self.calculate_chlorine_addition_options(
                            current_fc=chlorine,
                            target_fc=shock_level,
                            volume_liters=V,
                            bleach_percent=bleach,
                            cal_hypo_percent=cal_hypo_percent,
                            is_slam=True,
                            cya=cya,
                            split_threshold_ppm=10.0,
                            split_interval_hours=4
                        )
                        
                        # Store the dose data in sections['doses']
                        result['sections']['doses'] = dose_data
                        result['sections']['maintenance'].append("")
                        result['sections']['maintenance'].append("📋 NEXT: Top up chlorine to shock level")
                else:
                    result['sections']['maintenance'].append("")
                    result['sections']['maintenance'].append("✅ At proper shock level - maintain!")
            
            # SLAM maintenance steps
            result['sections']['maintenance'].append("")
            result['sections']['maintenance'].append("🔧 SLAM MAINTENANCE:")
            result['sections']['maintenance'].append("   • Test FC every 2-4 hours")
            result['sections']['maintenance'].append("   • Expect 2-4 ppm FC drop initially, decreasing as algae dies")
            result['sections']['maintenance'].append("   • Brush entire pool daily")
            result['sections']['maintenance'].append("   • Clean filter when pressure rises 25%")
            
            # Pump guidance
            V = config.get('pool_volume_liters', 7250) if config else 7250
            pump = config.get('pump_flow_rate') if config else None
            
            if pump and pump > 0:
                turnover_hours = V / pump
                result['sections']['pump_guidance'].append("⚡ CUSTOMIZED PUMP GUIDANCE (based on YOUR pump):")
                
                if turnover_hours <= 1:
                    min_runtime = turnover_hours * 2
                    rec_runtime = turnover_hours * 4
                    result['sections']['pump_guidance'].append(f"Your pump turns over your {V}L pool in just {turnover_hours:.1f} hours!")
                    result['sections']['pump_guidance'].append(f"Run pump for ONLY {min_runtime:.1f}-{rec_runtime:.1f} hours TOTAL per day")
                    result['sections']['pump_guidance'].append(f"Recommended: 2 cycles of {rec_runtime/2:.1f} hours each")
                    result['sections']['pump_guidance'].append("BRUSH before each restart to suspend debris")
                elif turnover_hours <= 3:
                    min_runtime = turnover_hours * 2
                    rec_runtime = turnover_hours * 4
                    result['sections']['pump_guidance'].append(f"Your pump turns over your {V}L pool in {turnover_hours:.1f} hours")
                    result['sections']['pump_guidance'].append(f"Run pump for {min_runtime:.1f}-{rec_runtime:.1f} hours TOTAL per day")
                    result['sections']['pump_guidance'].append("Run during and 1-2 hours after chlorine additions")
                    result['sections']['pump_guidance'].append("BRUSH before each restart")
                else:
                    min_runtime = turnover_hours * 2
                    rec_runtime = turnover_hours * 4
                    result['sections']['pump_guidance'].append(f"Your pump turns over your {V}L pool in {turnover_hours:.1f} hours")
                    result['sections']['pump_guidance'].append(f"For best results, aim for {rec_runtime:.0f} hours of runtime")
                    result['sections']['pump_guidance'].append(f"Consider running {rec_runtime/2:.0f} hours morning and evening")
                    result['sections']['pump_guidance'].append("BRUSHING is extra important with slower pumps")
            else:
                result['sections']['pump_guidance'].append("⚡ PUMP GUIDANCE (flow rate not provided):")
                result['sections']['pump_guidance'].append("Run pump for 3-4 cycles of 2-4 hours each day")
                result['sections']['pump_guidance'].append("Example: 2hr morning, 2hr afternoon, 2hr evening")
                result['sections']['pump_guidance'].append("BRUSH before each restart to suspend debris")
                result['sections']['pump_guidance'].append("")
                result['sections']['pump_guidance'].append("💡 For MORE ACCURATE guidance:")
                result['sections']['pump_guidance'].append("Enter your pump flow rate in 'Pool Setup' above")
            
            # Milestone
            result['sections']['milestone'].append("🎯 **KEY MILESTONE - Overnight FC Loss Test:**")
            result['sections']['milestone'].append("Test FC at night, then again in morning")
            result['sections']['milestone'].append("If FC loss ≤ 1.0 ppm: ✅ Algae is dead!")
            result['sections']['milestone'].append("**Use the 'Overnight Test' option above to indicate results**")
            result['sections']['milestone'].append("IMMEDIATELY switch to maintenance chlorine (Disable SLAM mode)")
            
            if pH is not None and pH > 7.4 and chlorine < 10:
                result['sections']['warnings'].append("⚠️ Note: pH adjustment recommended - see pH guidance above")
        
        # ===== POST-SLAM SECTION =====
        elif slam_context == 'post_slam':
            result['sections']['protocol'].append("🔄 POST-SLAM RECOVERY")
            result['sections']['protocol'].append(f"   Current FC: {chlorine:.1f} ppm" if chlorine else "   Current FC: Not tested")
            result['sections']['protocol'].append(f"   Target maintenance: {maintenance_min:.1f}-{maintenance_max:.1f} ppm")
            result['sections']['protocol'].append("")
            result['sections']['protocol'].append("📋 RECOVERY PROTOCOL:")
            
            # Pump guidance
            V = config.get('pool_volume_liters', 7250) if config else 7250
            pump = config.get('pump_flow_rate') if config else None
            
            if pump and pump > 0:
                turnover_hours = V / pump
                result['sections']['pump_guidance'].append("💧 FILTRATION (based on YOUR pump):")
                
                if turnover_hours <= 2:
                    result['sections']['pump_guidance'].append(f"Run pump {turnover_hours*6:.1f}-{turnover_hours*8:.1f} hours/day")
                    result['sections']['pump_guidance'].append(f"Recommended: 2-3 cycles of {turnover_hours*3:.0f} hours each")
                else:
                    result['sections']['pump_guidance'].append("Run pump as much as practical (aim for 12-16 hours/day)")
                    result['sections']['pump_guidance'].append(f"Your pump takes {turnover_hours:.1f}h for one turnover")
            else:
                result['sections']['pump_guidance'].append("💧 FILTRATION GUIDANCE:")
                result['sections']['pump_guidance'].append("Run pump 12-16 hours per day if possible")
                result['sections']['pump_guidance'].append("Split into 2-3 cycles (morning/afternoon/evening)")
            
            # Additional steps
            result['sections']['protocol'].append("")
            result['sections']['protocol'].append("   🎯 ADDITIONAL STEPS:")
            result['sections']['protocol'].append("   1. Maintain chlorine at target levels")
            result['sections']['protocol'].append("   2. Adjust pH via aeration if needed (avoid chemicals)")
            result['sections']['protocol'].append("   3. Brush daily to suspend dead algae")
            result['sections']['protocol'].append("   4. Clean filter when pressure rises 25%")
            result['sections']['protocol'].append("   5. Test daily until stable")
            result['sections']['protocol'].append("")
            result['sections']['protocol'].append("   💡 TIP: Milky water = dead algae. Patience!")
            result['sections']['protocol'].append("   • Water will clear in 3-7 days with good filtration")
        
        # ===== POST-SLAM FINAL SECTION =====
        elif slam_context == 'post_slam_final':
            result['sections']['protocol'].append("🔄 **POST-SLAM FINAL STAGE**")
            result['sections']['protocol'].append("   ✅ Overnight test passed (FC loss ≤ 1 ppm)")
            result['sections']['protocol'].append("   ⚪ Water still milky (dead algae filtering out)")
            result['sections']['protocol'].append("")
            result['sections']['protocol'].append("📋 **FINAL STAGE PROTOCOL:**")
            result['sections']['protocol'].append("   1. ✅ STOP adding shock-level chlorine")
            result['sections']['protocol'].append(f"   2. ✅ Maintain chlorine at {maintenance_min:.1f}-{maintenance_max:.1f} ppm")
            
            # Pump guidance
            V = config.get('pool_volume_liters', 7250) if config else 7250
            pump = config.get('pump_flow_rate') if config else None
            
            if pump and pump > 0:
                turnover_hours = V / pump
                result['sections']['pump_guidance'].append("")
                result['sections']['pump_guidance'].append("⚡ FILTRATION (based on YOUR pump):")
                
                if turnover_hours <= 2:
                    result['sections']['pump_guidance'].append(f"Run pump {turnover_hours*4:.1f}-{turnover_hours*6:.1f} hours/day")
                    result['sections']['pump_guidance'].append(f"Example: {turnover_hours*2:.0f}hr morning, {turnover_hours*2:.0f}hr evening")
                else:
                    result['sections']['pump_guidance'].append("Run pump 8-12 hours per day")
                    result['sections']['pump_guidance'].append(f"Your pump needs {turnover_hours:.1f}h per turnover")
            else:
                result['sections']['pump_guidance'].append("")
                result['sections']['pump_guidance'].append("⚡ FILTRATION GUIDANCE:")
                result['sections']['pump_guidance'].append("Run pump 8-12 hours per day")
                result['sections']['pump_guidance'].append("Split into 2 cycles (morning/evening)")
            
            result['sections']['protocol'].append("")
            result['sections']['protocol'].append("   3. ⚪ Continue pumping - filtering is #1 priority")
            result['sections']['protocol'].append("   4. ⚪ Backwash/clean filter when pressure rises 25%")
            result['sections']['protocol'].append("   5. ⚪ Brush daily to suspend particles")
            result['sections']['protocol'].append("")
            result['sections']['protocol'].append("   💡 **Key Change:** You're now in **maintenance mode**")
            result['sections']['protocol'].append("   • Filtering is now your #1 priority")
            result['sections']['protocol'].append("   • Can gradually reduce pump runtime as water clears")
            
            # Maintenance chlorine dose if needed
            target_fc = maintenance_max
            fc_needed = max(0, target_fc - current_fc)
            
            if fc_needed > 0 and config:
                V = config['pool_volume_liters']
                bleach = config['bleach_percent']
                cal_hypo_percent = config.get('cal_hypo_percent', 65.0)
                
                dose_data = self.calculate_chlorine_addition_options(
                    current_fc=current_fc,
                    target_fc=target_fc,
                    volume_liters=V,
                    bleach_percent=bleach,
                    cal_hypo_percent=cal_hypo_percent,
                    is_slam=False,
                    cya=cya,
                    split_threshold_ppm=5.0,
                    split_interval_hours=4
                )
                
                result['sections']['doses'] = dose_data
        
        return result


    # ==============================
    # pH + Alkalinity Combined Logic
    # ==============================
    
    def _calculate_ph_alkalinity_combined_actions(self, pH, alkalinity, config, chlorine=None, cya=None, slam_context='normal'):
        """Calculate combined pH and alkalinity actions with centralized safety."""
        actions = []
        V = config['pool_volume_liters']
        hcl = config['hcl_percent']
        pump = config.get('pump_flow_rate')
        
        ph_range = TARGET_RANGES['pH']
        ta_range = TARGET_RANGES['TA']
        
        normal_ph_low, normal_ph_high = ph_range['min'], ph_range['max']
        target_pH = ph_range['target']
        target_ta = ta_range['target']
        normal_ta_low, normal_ta_high = ta_range['min'], ta_range['max']
        
        acid_wait = self.get_waiting_time(V, pump, "acid")
        alk_wait = self.get_waiting_time(V, pump, "alkalinity")
        aer_wait = self.get_waiting_time(V, pump, "aeration")
        wait_acid = f"{acid_wait[0]:.1f}–{acid_wait[1]:.1f} hrs"
        wait_alk = f"{alk_wait[0]:.1f}–{alk_wait[1]:.1f} hrs"
        wait_aer = f"{aer_wait[0]:.1f}–{aer_wait[1]:.1f} hrs"
        
        ph_state = "low" if pH < normal_ph_low else "high" if pH > normal_ph_high else "normal"
        ta_state = "low" if alkalinity < normal_ta_low else "high" if alkalinity > normal_ta_high else "normal"
        
        # ===== SLAM MODE HANDLING =====
        if slam_context == 'during_slam':
            # During SLAM, only consider pH if FC < 10 ppm (reliable readings)
            if chlorine is not None and chlorine < 10:
                SLAM_PH_MIN = 7.2
                SLAM_PH_MAX = 7.4
                
                if pH > SLAM_PH_MAX:
                    # Calculate pH adjustment to optimal range
                    drop_needed = pH - SLAM_PH_MIN
                    raw_acid_ml = (drop_needed / 0.1) * CALCULATION_CONSTANTS['ACID_PH_DOSE'] * (V / 10000) * (31.45 / hcl)
                    
                    # Get safety guidance
                    acid_safety = self.calculate_safe_doses('acid', raw_acid_ml, V, config, context=slam_context)
                    safe_acid_ml = acid_safety['safe_amount']
                    
                    action_lines = [
                        f"⚡ SLAM OPTIMIZATION: pH too high ({pH:.2f}) for optimal SLAM",
                        f"   Target pH range: {SLAM_PH_MIN}-{SLAM_PH_MAX}",
                        f"   Current FC: {chlorine:.1f} ppm (<10 ppm - pH reading reliable)",
                        ""
                    ]
                    
                    if acid_safety['split_instructions']:
                        action_lines.append(f"   • {acid_safety['split_instructions']}")
                    else:
                        action_lines.append(f"   • Add {safe_acid_ml:.0f} ml {hcl}% HCl")
                    
                    action_lines.append("   • Wait 30 minutes, then retest pH")
                    
                    for warning in acid_safety['warnings']:
                        action_lines.append(f"   ⚠️ {warning}")
                    
                    action_lines.append("")
                    action_lines.append("   💡 TA adjustments can wait until after SLAM is complete.")
                    
                    actions.append("\n".join(action_lines))
                    return actions
            
            elif chlorine is not None and chlorine > 10:
                # pH unreliable - don't show combined actions
                return actions
        
        # ===== POST-SLAM SPECIAL HANDLING =====
        if slam_context == 'post_slam' and pH >= 7.0 and alkalinity >= 80:
            if pH < 7.4:
                ph_desc = f"Slightly low ({pH:.2f})"
                aeration_note = "🎯 IDEAL for aeration."
                aeration_time = "12-24 hours"
            elif pH > 7.6:
                ph_desc = f"Slightly high ({pH:.2f})"
                aeration_note = "⚠️ Monitor closely - aeration may raise pH further."
                aeration_time = "8-12 hours"
            else:
                ph_desc = f"Ideal ({pH:.2f})"
                aeration_note = "✅ Perfect range - maintain current conditions."
                aeration_time = "12-24 hours if needed"
            
            actions.append(
                f"   • POST-SLAM pH: {ph_desc}, TA normal ({alkalinity} ppm)\n"
                f"     {aeration_note} Run filter continuously and aerate {aeration_time}.\n"
                f"     🚫 Avoid chemicals - maintain chlorine effectiveness.\n"
                f"     💧 Keep filtering until crystal clear!"
            )
            return actions
        
        # ===== NORMAL MODE STATUS CHECK =====
        if slam_context == 'normal':
            ph_status = self.get_ph_status(pH)
            ta_status = self.get_ta_status(alkalinity)
            
            if ph_state == "normal" and ta_state == "normal":
                actions.append(f"   • pH: {ph_status}")
                actions.append(f"   • TA: {ta_status}")
                if pH >= 7.0 and alkalinity >= 80:
                    actions.append("     ✅ pH and TA in ideal range for stability")
                return actions
        
        # ===== COMBINED pH/TA ACTIONS FOR NORMAL AND POST-SLAM MODES =====
        
        # Scenario: pH normal/high + TA high
        if (ph_state == "normal" and ta_state == "high") or (ph_state == "high" and ta_state == "high"):
            ta_reduction_needed = alkalinity - target_ta
            safe_ta_reduction = min(ta_reduction_needed, 15)
            acid_ml = (safe_ta_reduction / 10) * CALCULATION_CONSTANTS['ACID_TA_DOSE'] * (V / 10000) * (31.45 / hcl)
            
            # Get safety guidance
            acid_safety = self.calculate_safe_doses('acid', acid_ml, V, config)
            
            expected_ph_drop = (safe_ta_reduction / 10) * 0.1
            
            context_prefix = "POST-SLAM " if slam_context == 'post_slam' else ""
            action_lines = [
                f"{context_prefix}pH{'normal' if ph_state == 'normal' else 'high'} ({pH:.2f}), TA high ({alkalinity} ppm):",
                "   Use stepwise acid/aeration to safely lower TA:",
                "   1. Add:"
            ]
            
            if acid_safety['split_instructions']:
                action_lines.append(f"      {acid_safety['split_instructions']}")
            else:
                action_lines.append(f"      {acid_ml:.0f}ml {hcl}% HCl")
            
            action_lines.append(f"      → Wait {wait_acid}")
            action_lines.append(f"   2. Aerate {wait_aer} to raise pH back to ~7.6")
            action_lines.append("   3. Retest pH & TA. Repeat until TA is 80-120 ppm")
            action_lines.append(f"   Note: This cycle should lower TA by ~{safe_ta_reduction} ppm (pH will drop ~{expected_ph_drop:.1f}).")
            
            for warning in acid_safety['warnings']:
                action_lines.append(f"   ⚠️ {warning}")
            
            actions.append("\n".join(action_lines))
        
        # Scenario: pH low + TA high
        elif ph_state == "low" and ta_state == "high":
            actions.append(
                f"pH low ({pH:.2f}), TA high ({alkalinity} ppm):\n"
                f"   Perfect for TA reduction! Aerate {wait_aer} to:\n"
                f"   1. Raise pH back to ~7.6\n"
                f"   2. Naturally lower TA by ~5-10 ppm\n"
                f"   Retest both. If TA still high, add small acid dose to lower pH to 7.0-7.2 and repeat."
            )
        
        # Scenario: pH low + TA low
        elif ph_state == "low" and ta_state == "low":
            ppm_up = target_ta - alkalinity
            baking_g = (ppm_up / 10) * CALCULATION_CONSTANTS['BAKING_SODA_TA_DOSE'] * (V / 10000)
            
            # Get safety guidance
            baking_safety = self.calculate_safe_doses('baking_soda', baking_g, V, config, context=slam_context)
            
            action_lines = [
                f"pH low ({pH:.2f}), TA low ({alkalinity} ppm):",
                f"   1. Add {baking_g:.0f}g Baking Soda → Wait {wait_alk}"
            ]
            
            for warning in baking_safety['warnings']:
                action_lines.append(f"      ⚠️ {warning}")
            
            action_lines.append(f"   2. Aerate {wait_aer} to raise pH → Retest")
            
            actions.append("\n".join(action_lines))
        
        # Scenario: pH low + TA normal
        elif ph_state == "low" and ta_state == "normal":
            if pH >= 7.0 and alkalinity >= 80:
                aeration_time = "12-24 hours" if pH >= 7.0 else "8-12 hours"
                actions.append(
                    f"pH slightly low ({pH:.2f}), TA normal ({alkalinity} ppm):\n"
                    f"   🎯 IDEAL for aeration. Aerate {aeration_time} to raise pH.\n"
                    f"   (Adding chemicals is unnecessary and will raise TA.)"
                )
            else:
                ph_up = target_pH - pH
                soda_g = (ph_up / 0.1) * CALCULATION_CONSTANTS['SODA_ASH_PH_DOSE'] * (V / 10000)
                ta_impact = self.ta_from_soda_ash(soda_g, V)
                
                # Get safety guidance
                soda_safety = self.calculate_safe_doses('soda_ash', soda_g, V, config, context=slam_context)
                
                action_lines = [
                    f"pH low ({pH:.2f}), TA normal:",
                    f"   • Preferred: Aerate {wait_aer}",
                    f"   • Chemical (raises TA): Add {soda_g:.0f}g Soda Ash (+{ta_impact:.0f} ppm TA) → Wait {wait_acid}"
                ]
                
                for warning in soda_safety['warnings']:
                    action_lines.append(f"     ⚠️ {warning}")
                
                actions.append("\n".join(action_lines))
        
        # Scenario: pH normal + TA low
        elif ph_state == "normal" and ta_state == "low":
            ppm_up = target_ta - alkalinity
            baking_g = (ppm_up / 10) * CALCULATION_CONSTANTS['BAKING_SODA_TA_DOSE'] * (V / 10000)
            
            # Get safety guidance
            baking_safety = self.calculate_safe_doses('baking_soda', baking_g, V, config)
            
            action_lines = [
                f"pH normal, TA low ({alkalinity} ppm):",
                f"   Add {baking_g:.0f}g Baking Soda → Wait {wait_alk} → Retest"
            ]
            
            for warning in baking_safety['warnings']:
                action_lines.append(f"   ⚠️ {warning}")
            
            actions.append("\n".join(action_lines))
        
        # Scenario: pH high + TA low
        elif ph_state == "high" and ta_state == "low":
            ph_down = pH - target_pH
            acid_ml = (ph_down / 0.1) * CALCULATION_CONSTANTS['ACID_PH_DOSE'] * (V / 10000) * (31.45 / hcl)
            
            ppm_up = target_ta - alkalinity
            baking_g = (ppm_up / 10) * CALCULATION_CONSTANTS['BAKING_SODA_TA_DOSE'] * (V / 10000)
            
            # Get safety guidance for both
            acid_safety = self.calculate_safe_doses('acid', acid_ml, V, config)
            baking_safety = self.calculate_safe_doses('baking_soda', baking_g, V, config)
            
            action_lines = [
                f"pH high ({pH:.2f}), TA low ({alkalinity} ppm):"
            ]
            
            # Acid step
            if acid_safety['split_instructions']:
                action_lines.append(f"   1. {acid_safety['split_instructions']} → Wait {wait_acid}")
            else:
                action_lines.append(f"   1. Add {acid_ml:.0f}ml {hcl}% HCl → Wait {wait_acid}")
            
            for warning in acid_safety['warnings']:
                action_lines.append(f"      ⚠️ {warning}")
            
            # Baking soda step
            if baking_safety['split_instructions']:
                action_lines.append(f"   2. {baking_safety['split_instructions']} → Wait {wait_alk}")
            else:
                action_lines.append(f"   2. Add {baking_g:.0f}g Baking Soda → Wait {wait_alk}")
            
            for warning in baking_safety['warnings']:
                action_lines.append(f"      ⚠️ {warning}")
            
            actions.append("\n".join(action_lines))
        
        # Scenario: pH high + TA normal
        elif ph_state == "high" and ta_state == "normal":
            ph_down = pH - target_pH
            acid_ml = (ph_down / 0.1) * CALCULATION_CONSTANTS['ACID_PH_DOSE'] * (V / 10000) * (31.45 / hcl)
            
            # Get safety guidance
            acid_safety = self.calculate_safe_doses('acid', acid_ml, V, config)
            
            action_lines = [f"pH high ({pH:.2f}):"]
            
            if acid_safety['split_instructions']:
                action_lines.append(f"   {acid_safety['split_instructions']} → Wait {wait_acid}")
            else:
                action_lines.append(f"   Add {acid_ml:.0f}ml {hcl}% HCl → Wait {wait_acid}")
            
            for warning in acid_safety['warnings']:
                action_lines.append(f"   ⚠️ {warning}")
            
            actions.append("\n".join(action_lines))
        
        return actions
    
    # ==============================
    # pH Only Logic
    # ==============================
    
    def _calculate_ph_only_actions(self, pH, config, alkalinity=None, chlorine=None, cya=None, slam_context='normal'):
        """Calculate pH-only actions - PRIMARY source for chemical doses."""
        actions = []
        V = config['pool_volume_liters']
        hcl = config['hcl_percent']
        pump = config.get('pump_flow_rate')
        
        ph_range = TARGET_RANGES['pH']
        target = ph_range['target']
        low, high = ph_range['min'], ph_range['max']
        
        acid_wait = self.get_waiting_time(V, pump, "acid")
        aer_wait = self.get_waiting_time(V, pump, "aeration")
        wait_acid = f"{acid_wait[0]:.1f}–{acid_wait[1]:.1f} hrs"
        wait_aer = f"{aer_wait[0]:.1f}–{aer_wait[1]:.1f} hrs"
        
        if slam_context == 'during_slam':
            if chlorine is not None and chlorine > 10:
                if cya is None or cya == 0:
                    shock_level = 10.0
                elif cya < 30:
                    shock_level = 10.0
                else:
                    shock_level = cya * 0.4
                actions.append(
                    f"SLAM ACTIVE: pH reading ({pH:.2f}) may be inaccurate (FC > 10 ppm)\n"
                    f"   • Focus on maintaining shock level of {shock_level:.1f} ppm\n"
                    f"   • Adjust pH only if you're certain it's accurate"
                )
                return actions
            
            # ENHANCED GUIDANCE for when chlorine < 10 during SLAM
            if chlorine is not None and chlorine < 10:
                # Calculate shock level based on CYA
                if cya is None or cya == 0:
                    shock_level = 10.0
                elif cya < 30:
                    shock_level = 10.0
                else:
                    shock_level = cya * 0.4
                
                # Define SLAM optimal pH range (7.2-7.4)
                SLAM_PH_MIN = 7.2
                SLAM_PH_MAX = 7.4
                
                # Check if pH needs adjustment
                if pH > SLAM_PH_MAX:
                    # Calculate pH adjustment to 7.2
                    drop_needed = pH - SLAM_PH_MIN
                    raw_acid_ml = (drop_needed / 0.1) * CALCULATION_CONSTANTS['ACID_PH_DOSE'] * (V / 10000) * (31.45 / hcl)
                    
                    # Get safety guidance from centralized helper
                    acid_safety = self.calculate_safe_doses('acid', raw_acid_ml, V, config, context=slam_context)
                    safe_acid_ml = acid_safety['safe_amount']
                    
                    fc_needed = max(0, shock_level - chlorine)
                    
                    # Build the guidance message
                    guidance = [
                        f"⚡ pH OUTSIDE OPTIMAL WINDOW ({pH:.2f}) - ADJUST pH FIRST:",
                        f"   Current FC: {chlorine:.1f} ppm",
                        f"   Target shock level: {shock_level:.1f} ppm",
                        f"   SLAM optimal pH: {SLAM_PH_MIN}-{SLAM_PH_MAX}",
                        "",
                        "   STEP 1 - LOWER pH TO 7.2:"
                    ]
                    
                    if acid_safety['split_instructions']:
                        guidance.append(f"   • {acid_safety['split_instructions']}")
                    else:
                        guidance.append(f"   • Add {safe_acid_ml:.0f} ml {hcl}% HCl")
                    
                    guidance.append("   • Wait 30 minutes, then retest pH")
                    
                    for warning in acid_safety['warnings']:
                        guidance.append(f"   ⚠️ {warning}")
                    
                    if fc_needed > 0:
                        # Chlorine dose calculations (these are fine, they use their own safety)
                        bleach = config['bleach_percent']
                        cal_hypo_percent = config.get('cal_hypo_percent', 65.0)
                        
                        liq_ml = fc_needed * CALCULATION_CONSTANTS['LIQUID_CHLORINE_DOSE'] * (V / 10000) * (12.5 / bleach)
                        base_dose = CALCULATION_CONSTANTS['CAL_HYPO_DOSE']
                        gran_g = fc_needed * base_dose * (V / 10000) * (65 / cal_hypo_percent)
                        
                        # Get safety guidance for chlorine options
                        cal_hypo_config = config.copy()
                        cal_hypo_config['ppm_increase'] = fc_needed
                        cal_hypo_safety = self.calculate_safe_doses('cal_hypo', gran_g, V, cal_hypo_config, context=slam_context)
                        liq_safety = self.calculate_safe_doses('liquid_chlorine', liq_ml, V, config, context=slam_context)
                        
                        guidance.append("")
                        guidance.append("   STEP 2 - AFTER pH IS 7.2-7.4, ADD CHLORINE:")
                        
                        if cal_hypo_safety['split_instructions']:
                            guidance.append(f"   • {cal_hypo_safety['split_instructions']}")
                        else:
                            guidance.append(f"   • Add {gran_g:.0f} g {cal_hypo_percent}% cal-hypo")
                        
                        if liq_safety['split_instructions']:
                            guidance.append(f"   • OR {liq_safety['split_instructions']}")
                        else:
                            guidance.append(f"   • OR Add {liq_ml:.0f} ml {bleach}% liquid chlorine")
                        
                        all_warnings = cal_hypo_safety['warnings'] + liq_safety['warnings']
                        if all_warnings:
                            guidance.append("")
                            for warning in all_warnings:
                                guidance.append(f"   ⚠️ {warning}")
                    
                    actions.append("\n".join(guidance))
                    return actions
            
            # Original pH > 7.8 check for SLAM (fallback)
            if pH > 7.8:
                quick_drop = min(pH - 7.8, 0.4)
                acid_ml = (quick_drop / 0.1) * CALCULATION_CONSTANTS['ACID_PH_DOSE'] * (V / 10000) * (31.45 / hcl)
                actions.append(
                    f"SLAM ACTIVE: pH too high ({pH:.2f}) for effective chlorine\n"
                    f"   Quick adjustment to ~7.8: Add {acid_ml:.0f} ml {hcl}% HCl\n"
                    f"   → Wait 30 min, retest pH, then continue SLAM"
                )
                return actions
        
        if slam_context == 'post_slam' and pH >= 7.0 and (alkalinity is None or alkalinity >= 80):
            aeration_time = "12-24 hours" if pH >= 7.0 else "8-12 hours"
            actions.append(
                f"   • POST-SLAM pH: Slightly low ({pH:.2f})\n"
                f"     🎯 IDEAL for aeration. Run filter continuously and aerate {aeration_time}.\n"
                f"     🚫 Avoid chemicals - they can affect chlorine effectiveness.\n"
                f"     💧 Keep filtering until crystal clear!"
            )
            return actions
        
        if chlorine is not None and chlorine < 0.5 and pH > 7.8:
            quick_drop = min(pH - 7.8, 0.6)
            acid_ml = (quick_drop / 0.1) * CALCULATION_CONSTANTS['ACID_PH_DOSE'] * (V / 10000) * (31.45 / hcl)
            high_dose_note = self.get_high_dose_note(acid_ml, V, pump)
            
            if cya is not None:
                if cya == 0:
                    shock_target = 10.0
                    cya_note = " (no CYA - use 10 ppm)"
                elif cya < 30:
                    shock_target = 10.0
                    cya_note = f" (CYA low at {cya} ppm - use 10 ppm)"
                else:
                    shock_target = cya * 0.4
                    cya_note = f" (for CYA {cya} ppm)"
            else:
                shock_target = 10.0
                cya_note = " (CYA unknown - assume 10 ppm)"
            
            actions.append(
                f"🚨 EMERGENCY: Chlorine at {chlorine:.1f} ppm, algae risk high\n"
                f"   1. Quick pH adjustment: Add {acid_ml:.0f} ml {hcl}% HCl{high_dose_note} → Wait 1 hr\n"
                f"   2. RETEST pH. Once pH ≤ 7.8, BEGIN SLAM IMMEDIATELY\n"
                f"   Target shock level: {shock_target:.1f} ppm{cya_note}"
            )
            return actions
        
        if slam_context == 'normal':
            ph_status = self.get_ph_status(pH)
            actions.append(f"   • pH: {ph_status}")
            
            if pH >= low and pH <= high:
                actions.append("     ✅ In target range (7.2-7.8)")
                return actions
        
        if pH > high:
            drop = pH - target
            
            safe_drop = drop
            safety_note = ""
            
            if alkalinity is not None:
                if alkalinity < 90:
                    safe_drop = min(drop, 0.3)
                    safety_note = f"\n   ⚠️ VERY LOW TA ({alkalinity} ppm): Maximum 0.3 pH drop for safety"
                elif alkalinity < 100:
                    safe_drop = min(drop, 0.5)
                    safety_note = f"\n   ⚠️ LOW TA ({alkalinity} ppm): Limiting to 0.5 pH drop"
            
            acid_ml = (safe_drop / 0.1) * CALCULATION_CONSTANTS['ACID_PH_DOSE'] * (V / 10000) * (31.45 / hcl)
            
            # Use centralized safety helper for acid
            acid_safety = self.calculate_safe_doses('acid', acid_ml, V, config)
            
            warning_msg = ""
            if not acid_safety['single_dose_possible']:
                warning_msg = f"\n   {acid_safety['split_instructions']}"
            
            context_prefix = "POST-SLAM " if slam_context == 'post_slam' else ""
            actions.append(
                f"{context_prefix}pH high ({pH:.2f}){safety_note}:\n"
                f"   Add {acid_safety['safe_amount']:.0f} ml {hcl}% HCl{warning_msg}\n"
                f"   → Wait 1 hour, RETEST pH before adding more acid"
            )
            
            for warning in acid_safety['warnings']:
                if warning not in str(actions[-1]):
                    actions.append(f"   ⚠️ {warning}")
        
        elif pH < low:
            rise = target - pH
            
            if pH >= 7.0:
                soda_g = (rise / 0.1) * CALCULATION_CONSTANTS['SODA_ASH_PH_DOSE'] * (V / 10000)
                
                # Use centralized safety helper for soda ash
                soda_safety = self.calculate_safe_doses('soda_ash', soda_g, V, config)
                
                context_prefix = "POST-SLAM " if slam_context == 'post_slam' else ""
                action_text = (
                    f"{context_prefix}pH slightly low ({pH:.2f}):\n"
                    f"   • **RECOMMENDED:** Aerate {wait_aer} to raise pH.\n"
                    f"   • Chemical (Only if aeration not possible): Add {soda_g:.0f} g Soda Ash → Wait {wait_acid}\n"
                    f"     **Warning:** Will raise TA. Retest both pH and TA."
                )
                actions.append(action_text)
                
                for warning in soda_safety['warnings']:
                    actions.append(f"   ⚠️ {warning}")
            else:
                soda_g = (rise / 0.1) * CALCULATION_CONSTANTS['SODA_ASH_PH_DOSE'] * (V / 10000)
                
                # Use centralized safety helper for soda ash
                soda_safety = self.calculate_safe_doses('soda_ash', soda_g, V, config)
                
                action_text = (
                    f"pH low ({pH:.2f}):\n"
                    f"   • Safer: Aerate {wait_aer}\n"
                    f"   • Chemical: Add {soda_g:.0f} g Soda Ash → Wait {wait_acid}\n"
                    f"     (will raise TA – retest both)"
                )
                actions.append(action_text)
                
                for warning in soda_safety['warnings']:
                    actions.append(f"   ⚠️ {warning}")
        
        return actions
    
    # ==============================
    # TA Only Logic
    # ==============================
    
    def _calculate_ta_only_actions(self, alkalinity, config, slam_context='normal'):
        """Calculate TA-only actions."""
        actions = []
        V = config['pool_volume_liters']
        hcl = config['hcl_percent']
        pump = config.get('pump_flow_rate')
        
        ta_range = TARGET_RANGES['TA']
        target = ta_range['target']
        low, high = ta_range['min'], ta_range['max']
        
        acid_wait = self.get_waiting_time(V, pump, "acid")
        alk_wait = self.get_waiting_time(V, pump, "alkalinity")
        aer_wait = self.get_waiting_time(V, pump, "aeration")
        wait_acid = f"{acid_wait[0]:.1f}–{acid_wait[1]:.1f} hrs"
        wait_alk = f"{alk_wait[0]:.1f}–{alk_wait[1]:.1f} hrs"
        wait_aer = f"{aer_wait[0]:.1f}–{aer_wait[1]:.1f} hrs"
        
        if slam_context == 'normal':
            ta_status = self.get_ta_status(alkalinity)
            actions.append(f"   • TA: {ta_status}")
            
            if alkalinity >= low and alkalinity <= high:
                actions.append("     ✅ In target range (80-120 ppm)")
                return actions
        
        if alkalinity < low:
            ppm_up = target - alkalinity
            baking_g = (ppm_up / 10) * CALCULATION_CONSTANTS['BAKING_SODA_TA_DOSE'] * (V / 10000)
            context_prefix = "POST-SLAM " if slam_context == 'post_slam' else ""
            actions.append(
                f"{context_prefix}Alkalinity low ({alkalinity} ppm) – pH unknown:\n"
                f"   Add {baking_g:.0f} g Baking Soda → Wait {wait_alk}\n"
                f"   → Retest both pH and alkalinity"
            )
        elif alkalinity > high:
            ppm_down = alkalinity - target
            acid_ml = (ppm_down / 10) * CALCULATION_CONSTANTS['ACID_TA_DOSE'] * (V / 10000) * (31.45 / hcl)
            high_dose_note = self.get_high_dose_note(acid_ml, V, pump)
            context_prefix = "POST-SLAM " if slam_context == 'post_slam' else ""
            actions.append(
                f"{context_prefix}Alkalinity high ({alkalinity} ppm) – pH unknown:\n"
                f"   CAUTION: Acid will lower pH\n"
                f"   Add {acid_ml:.0f} ml {hcl}% HCl{high_dose_note} → Wait {wait_acid}\n"
                f"   → TEST pH FIRST — may need aeration {wait_aer} after"
            )
        
        return actions
    
    # ==============================
    # Chlorine Actions
    # ==============================
    
    def _calculate_chlorine_actions(self, chlorine, config, ph_out_of_range=False, cya=None, slam_context='normal'):
        """Calculate chlorine actions with centralized safety."""
        actions = []
        V = config['pool_volume_liters']
        bleach = config['bleach_percent']
        cal_hypo_percent = config.get('cal_hypo_percent', 65.0)
        pump = config.get('pump_flow_rate')
        
        if chlorine is None:
            return actions
        
        # Calculate target levels based on context
        if slam_context in ['during_slam', 'pre_slam']:
            # SLAM mode - target shock level
            if cya is None or cya == 0:
                target_level = 10.0
            elif cya < 30:
                target_level = 10.0
            else:
                target_level = cya * 0.4
            threshold = target_level * 0.95
            is_slam_context = True
        else:
            # Maintenance mode (normal, post_slam, post_slam_final) - target maintenance level
            if cya is None or cya == 0:
                target_level = 3.0  # Default max maintenance
            elif cya < 30:
                target_level = cya * 0.15
            else:
                target_level = cya * 0.15
            threshold = target_level * 0.9  # 90% of target for maintenance
            is_slam_context = False
        
        # Only add dose if chlorine is below threshold
        if chlorine < threshold:
            ppm_up = target_level - chlorine
            
            # Get the dose data dictionary
            dose_data = self.calculate_chlorine_addition_options(
                current_fc=chlorine,
                target_fc=target_level,
                volume_liters=V,
                bleach_percent=bleach,
                cal_hypo_percent=cal_hypo_percent,
                is_slam=is_slam_context,
                cya=cya,
                split_threshold_ppm=10.0 if is_slam_context else 5.0,
                split_interval_hours=4
            )
            
            # Format the dose data into readable strings
            if not dose_data.get('skip', False):
                # Add the main message
                if is_slam_context:
                    actions.append(f"Raise FC to SLAM level ({target_level:.1f} ppm):")
                else:
                    actions.append(f"Raise FC to {target_level:.1f} ppm:")
                
                # Add the options
                liquid = dose_data['liquid']
                cal_hypo = dose_data['cal_hypo']
                actions.append(f"• Add ≈ {liquid['amount']:.0f} {liquid['unit']} of {liquid['percentage']}% liquid chlorine")
                actions.append(f"• OR add ≈ {cal_hypo['amount']:.0f} {cal_hypo['unit']} of {cal_hypo['percentage']}% calcium hypochlorite")
                
                # Add split info if needed
                if dose_data.get('split_info', {}).get('needed', False):
                    split = dose_data['split_info']
                    actions.append("")
                    actions.append(f"Large raise required → split into ≈ {split['doses']} doses:")
                    actions.append(f"  • ≈ {split['per_dose_liquid']:.0f} ml liquid chlorine   OR   ≈ {split['per_dose_cal_hypo']:.0f} g Cal-Hypo per dose")
                    actions.append(f"  • Wait {split['interval']}–6 hours, re-test FC, then add next dose if needed")
                
                # Add notes
                if dose_data.get('notes'):
                    actions.append("")
                    actions.append("Notes on your options:")
                    for note in dose_data['notes']:
                        actions.append(f"• {note}")
                
                # Add warnings
                if dose_data.get('warnings'):
                    for warning in dose_data['warnings']:
                        actions.append(f"⚠️ {warning}")
                
                # Add wait time
                wait_info = self.get_waiting_time(V, pump, "acid")
                wait_text = f"{wait_info[0]:.1f}–{wait_info[1]:.1f} hrs (pump running)" if pump else "2–4 hrs"
                actions.append(f"→ Retest FC in {wait_text}")
        
        return actions

    def calculate_chlorine_addition_options(
        self,
        current_fc: float,
        target_fc: float,
        volume_liters: float,
        bleach_percent: float,
        cal_hypo_percent: float = 65.0,
        is_slam: bool = False,
        cya: Optional[float] = None,
        split_threshold_ppm: float = 10.0,
        split_interval_hours: int = 4,
    ) -> Dict[str, Any]:
        """
        Returns structured chlorine dose data for the builder to format.
        """
        if current_fc >= target_fc * 0.95:
            return {
                'skip': True,
                'message': f"Current FC is {current_fc:.1f} ppm — already at or above target"
            }

        delta = target_fc - current_fc
        if delta <= 0:
            return {'skip': True, 'message': "No additional chlorine needed"}

        scale = volume_liters / 10000.0

        # Liquid bleach calculation
        ml_per_ppm_bleach = 80.0 * (12.5 / bleach_percent)
        ml_bleach = delta * scale * ml_per_ppm_bleach
        ml_bleach = round(ml_bleach / 10) * 10

        # Cal-Hypo calculation
        g_per_ppm_calhypo = 15.38 * (65.0 / cal_hypo_percent)
        g_calhypo = delta * scale * g_per_ppm_calhypo
        g_calhypo = round(g_calhypo / 10) * 10

        result = {
            'target_fc': target_fc,
            'current_fc': current_fc,
            'delta': delta,
            'liquid': {
                'amount': ml_bleach,
                'unit': 'ml',
                'percentage': bleach_percent
            },
            'cal_hypo': {
                'amount': g_calhypo,
                'unit': 'g',
                'percentage': cal_hypo_percent
            },
            'is_slam': is_slam,
            'notes': [],
            'warnings': []
        }

        # Check if split dosing is needed
        if delta > split_threshold_ppm:
            doses = max(2, int(delta / split_threshold_ppm) + 1)
            per_dose_delta = delta / doses
            per_dose_ml = round(per_dose_delta * scale * ml_per_ppm_bleach / 10) * 10
            per_dose_g = round(per_dose_delta * scale * g_per_ppm_calhypo / 10) * 10
            
            result['split_info'] = {
                'needed': True,
                'doses': doses,
                'per_dose_liquid': per_dose_ml,
                'per_dose_cal_hypo': per_dose_g,
                'interval': split_interval_hours
            }

        # Add standard notes (as raw text, builder will format)
        result['notes'].append("Liquid chlorine adds almost no CYA and no calcium")
        result['notes'].append("Cal-Hypo adds a small amount of both CYA and calcium per dose")

        if is_slam:
            result['notes'].append("Maintain pH 7.2–7.5 while FC > 10 ppm (test often)")
            result['notes'].append("Brush walls/floor daily + run pump/filter 24/7")

        if cya is None or cya < 20:
            result['warnings'].append("CYA is low or unknown — re-test CYA soon for accurate SLAM/maintenance targets")

        return result
    

    # ==============================
    # CYA Actions
    # ==============================
    
    def _calculate_cya_actions(self, cya, config, is_post_slam=False, slam_context='normal'):
        """Calculate CYA actions."""
        actions = []
        V = config['pool_volume_liters']
        if cya is None:
            return actions
        
        cya_range = TARGET_RANGES['CYA']
        low, high = cya_range['min'], cya_range['max']
        
        if slam_context == 'normal':
            cya_status = self.get_cya_status(cya)
            actions.append(f"   • CYA: {cya_status}")
            
            if cya >= low and cya <= high:
                actions.append("     ✅ In target range (30-50 ppm)")
                return actions
        
        if cya < low:
            ppm_up = low - cya
            cya_g = ppm_up * CALCULATION_CONSTANTS['CYA_DOSE'] * (V / 10000)
            
            if is_post_slam or slam_context == 'post_slam':
                actions.append(
                    f"   • POST-SLAM CYA: Low ({cya} ppm) → Shock level is only {cya * 0.4:.1f} ppm\n"
                    f"     Add {cya_g:.0f} g Cyanuric Acid (dissolve in sock in skimmer)\n"
                    "     → Wait 24–48 hrs with pump running\n"
                    f"     💡 After adding CYA, maintain chlorine at {cya * 0.075:.1f}-{cya * 0.15:.1f} ppm"
                )
            else:
                if slam_context in ['pre_slam', 'during_slam']:
                    actions.append(
                        f"CYA low ({cya} ppm) → Add {cya_g:.0f} g Cyanuric Acid\n"
                        "   → Wait 24–48 hrs with pump running\n"
                        "   💡 **TIMING CRITICAL:**\n"
                        "      1. Complete SLAM first (pass overnight FC loss test)\n"
                        "      2. Wait for water to become crystal clear\n"
                        "      3. THEN add CYA\n"
                        "      (Adding CYA mid-SLAM raises your required shock level!)"
                    )
                else:
                    actions.append(
                        f"CYA low ({cya} ppm) → Add {cya_g:.0f} g Cyanuric Acid\n"
                        f"   → Wait 24–48 hrs with pump running"
                    )
        
        elif cya > high:
            excess = cya - high
            pct = (excess / cya) * 100
            water_L = (pct / 100) * V
            actions.append(
                f"CYA high ({cya} ppm) → Replace {water_L:.0f} L ({pct:.1f}%) of water"
            )
        
        return actions
    
    # ==============================
    # Calcium Actions
    # ==============================
    
    def _calculate_calcium_actions(self, calcium, config, slam_context='normal'):
        """Calculate calcium actions."""
        actions = []
        V = config['pool_volume_liters']
        
        # During SLAM, calcium is not a priority - return empty actions
        if slam_context in ['during_slam', 'pre_slam']:
            return actions
        
        if calcium is None:
            return actions
        
        ch_range = TARGET_RANGES['CH']
        low, high = ch_range['min'], ch_range['max']
        
        if slam_context == 'normal':
            ca_status = self.get_calcium_status(calcium)
            actions.append(f"   • Calcium: {ca_status}")
            
            if calcium >= low and calcium <= high:
                actions.append("     ✅ In target range (200-400 ppm)")
                return actions
        
        if calcium < low:
            ppm_up = low - calcium
            ca_g = ppm_up * CALCULATION_CONSTANTS['CALCIUM_DOSE'] * (V / 10000)
            actions.append(
                f"Calcium low ({calcium} ppm) → Add {ca_g:.0f} g Calcium Chloride\n"
                f"   → Wait 4–6 hrs"
            )
        
        elif calcium > high:
            if calcium == 0:
                return actions
            excess = calcium - high
            pct = (excess / calcium) * 100
            water_L = (pct / 100) * V
            actions.append(
                f"Calcium high ({calcium} ppm) → Replace {water_L:.0f} L ({pct:.1f}%) of water"
            )
        
        return actions
    
    # ==============================
    # Main Adjust Function
    # ==============================
    
    def adjust_pool(self, readings, config, water_clarity="crystal_clear", 
                is_slam_mode=False, overnight_test="not_tested"):
        """
        Main function to analyze pool chemistry and generate recommendations.
        Uses GuidanceBuilder for structured output.
        """
        pH = readings.get('pH')
        TA = readings.get('alkalinity')
        Cl = readings.get('chlorine')
        CYA = readings.get('cya')
        CH = readings.get('calcium')
        
        local_config = {
            'pool_volume_liters': config.get('pool_volume_liters', 7250),
            'hcl_percent': config.get('hcl_percent', 31.45),
            'bleach_percent': config.get('bleach_percent', 12.5),
            'cal_hypo_percent': config.get('cal_hypo_percent', 65.0),
            'pump_flow_rate': config.get('pump_flow_rate'),
            'calcium_reading': CH,
            'is_slam_mode': is_slam_mode
        }
        
        try:
            # Initialize builder
            builder = GuidanceBuilder()
            
            # Add header
            builder.add_header()
            
            # Add parameters
            pump = local_config.get('pump_flow_rate')
            slam_status = "ACTIVE" if is_slam_mode else "INACTIVE"
            clarity_display = get_clarity_display_name(water_clarity)
            
            builder.add_parameters(
                volume=local_config['pool_volume_liters'],
                pump=pump if pump and pump > 0 else None,
                slam_mode=slam_status,
                clarity=clarity_display,
                overnight_test=overnight_test
            )
            
            # Detect SLAM context
            if is_slam_mode:
                slam_context = 'during_slam'
            else:
                slam_context = self.detect_slam_context(pH, Cl, CYA, water_clarity, overnight_test, is_slam_mode)
            
            # Add mode
            builder.add_mode(slam_context)
            
            # ===== COLLECT RECOMMENDATIONS BY TYPE =====
            chem_readings = {}
            chem_statuses = {}
            regular_doses = []  # This will now hold DICT data, not strings
            pump_guidance = []  # This will hold raw strings without bullets
            maintenance_tips = []
            
            # Chemistry statuses (this part stays the same)
            if pH is not None:
                chem_readings['pH'] = pH
                chem_statuses['pH'] = self.get_ph_status(pH, slam_context)
            if TA is not None:
                chem_readings['TA'] = TA
                chem_statuses['TA'] = self.get_ta_status(TA)
            if Cl is not None:
                chem_readings['Cl'] = Cl
                chem_statuses['Cl'] = self.get_chlorine_status(Cl, CYA, slam_context)
            if CYA is not None:
                chem_readings['CYA'] = CYA
                chem_statuses['CYA'] = self.get_cya_status(CYA, slam_context)
            if CH is not None:
                chem_readings['CH'] = CH
                chem_statuses['CH'] = self.get_calcium_status(CH)
            
            # Add chemistry analysis
            builder.add_chemistry_analysis(chem_readings, chem_statuses)
            
            # ===== SLAM CONTENT COLLECTION =====
            if slam_context in ['pre_slam', 'during_slam', 'post_slam', 'post_slam_final']:
                slam_data = self.get_slam_guidance_structured(Cl, CYA, pH, water_clarity, local_config, slam_context=slam_context)
                
                # SLAM DOSES - now passing raw data dict
                if slam_data['sections']['doses'] and not slam_data['sections']['doses'].get('skip'):
                    builder.add_slam_doses(slam_data['sections']['doses'])
                
                # SLAM MAINTENANCE - raw strings without bullets
                if slam_data['sections']['maintenance']:
                    valid_maintenance = [m for m in slam_data['sections']['maintenance'] if m and m.strip()]
                    if valid_maintenance:
                        builder.add_slam_maintenance(valid_maintenance)
                
                # KEY MILESTONE - raw strings without bullets
                if slam_data['sections']['milestone']:
                    valid_milestone = [m for m in slam_data['sections']['milestone'] if m and m.strip()]
                    if valid_milestone:
                        builder.add_key_milestone("KEY MILESTONE", valid_milestone)
                
                # PUMP GUIDANCE - collect raw strings for later
                if slam_data['sections']['pump_guidance']:
                    valid_guidance = [g for g in slam_data['sections']['pump_guidance'] if g and g.strip()]
                    pump_guidance.extend(valid_guidance)
                
                # PROTOCOL STEPS - these will go into regular_doses as structured data
                if slam_data['sections']['protocol']:
                    # Convert protocol steps to structured dose format
                    for step in slam_data['sections']['protocol']:
                        if step and step.strip():
                            regular_doses.append({
                                'type': 'protocol',
                                'action': step,  # Raw step without numbers
                                'details': [],
                                'warnings': []
                            })

            # ===== REGULAR CHEMICAL DOSES COLLECTION =====
            # pH and alkalinity actions
            if pH is not None and TA is not None:
                combined_actions = self._calculate_ph_alkalinity_combined_actions(
                    pH, TA, local_config, chlorine=Cl, cya=CYA, slam_context=slam_context
                )
                # Convert string actions to dict format
                for action in combined_actions:
                    if action and isinstance(action, str):
                        regular_doses.append({
                            'type': 'combined',
                            'action': action,
                            'details': [],
                            'warnings': []
                        })
            
            elif pH is not None:
                ph_actions = self._calculate_ph_only_actions(
                    pH, local_config, alkalinity=TA, chlorine=Cl, cya=CYA, slam_context=slam_context
                )
                for action in ph_actions:
                    if action and isinstance(action, str):
                        regular_doses.append({
                            'type': 'ph',
                            'action': action,
                            'details': [],
                            'warnings': []
                        })
            
            elif TA is not None:
                ta_actions = self._calculate_ta_only_actions(TA, local_config, slam_context=slam_context)
                for action in ta_actions:
                    if action and isinstance(action, str):
                        regular_doses.append({
                            'type': 'ta',
                            'action': action,
                            'details': [],
                            'warnings': []
                        })
            
            # Chlorine actions (for maintenance mode and non-SLAM contexts)
            if Cl is not None and slam_context not in ['pre_slam', 'during_slam']:
                chlorine_actions = self._calculate_chlorine_actions(
                    Cl, local_config, False, CYA, slam_context=slam_context
                )
                for action in chlorine_actions:
                    if action and isinstance(action, str):
                        regular_doses.append({
                            'type': 'chlorine',
                            'action': action,
                            'details': [],
                            'warnings': []
                        })
            
            # CYA actions
            if CYA is not None:
                cya_actions = self._calculate_cya_actions(CYA, local_config, 
                                                        is_post_slam=(slam_context == 'post_slam'),
                                                        slam_context=slam_context)
                for action in cya_actions:
                    if action and isinstance(action, str):
                        regular_doses.append({
                            'type': 'cya',
                            'action': action,
                            'details': [],
                            'warnings': []
                        })
            
            # Calcium actions
            if CH is not None and slam_context not in ['during_slam', 'pre_slam']:
                calcium_actions = self._calculate_calcium_actions(CH, local_config, slam_context=slam_context)
                for action in calcium_actions:
                    if action and isinstance(action, str):
                        regular_doses.append({
                            'type': 'calcium',
                            'action': action,
                            'details': [],
                            'warnings': []
                        })
            
            # Add regular doses if any
            if regular_doses:
                builder.add_doseages(regular_doses)
            
            # ===== PUMP GUIDANCE =====
            V = local_config['pool_volume_liters']
            pump = local_config.get('pump_flow_rate')
            turnover_hours = None
            
            if not pump_guidance:  # If we didn't get any from SLAM guidance
                if pump and pump > 0:
                    turnover_hours = V / pump
                    pump_guidance = [
                        f"Your pump turns over your {V:.0f}L pool in {turnover_hours:.1f} hours",
                        f"Recommended runtime: {turnover_hours*2:.1f}-{turnover_hours*4:.1f} hours TOTAL per day",
                        "Split into 2 cycles for best results"
                    ]
                else:
                    pump_guidance = [
                        "For best results, run pump 8-12 hours per day",
                        "Split into 2-3 cycles (morning/afternoon/evening)",
                        "Enter pump flow rate for customized guidance"
                    ]
            
            # Add pump guidance with structured format
            builder.add_pump_guidance({
                'has_pump_data': pump is not None and pump > 0,
                'turnover_hours': turnover_hours if pump and pump > 0 else None,
                'guidance': pump_guidance  # Raw strings without bullets
            })
            
            # ===== WATER CLARITY GUIDANCE =====
            if water_clarity != "crystal_clear":
                clarity_guidance = []
                
                if water_clarity in ["slightly_cloudy", "cloudy"]:
                    clarity_guidance = [
                        "Monitor chlorine levels closely",
                        "Consider running filter longer",
                        "Check and clean filter media"
                    ]
                elif water_clarity == "milky":
                    if slam_context == 'post_slam_final':
                        clarity_guidance = [
                            "Overnight test passed - you're in final filtering stage",
                            "Focus should shift to filtration, not chlorine",
                            "Run filter 24/7, or as long as possible, until clear"
                        ]
                    else:
                        clarity_guidance = [
                            "This is normal after SLAM - dead algae",
                            "Run filter 24/7 until clear",
                            "Patience! Clearing can take 3-7 days"
                        ]
                elif water_clarity in ["green_algae", "black_algae"]:
                    clarity_guidance = [
                        "Brush affected areas daily",
                        "INITIATE SLAM PROCESS if not already started",
                        "Test and adjust pH to 7.2-7.8 first"
                    ]
                
                builder.add_water_clarity({
                    'status': get_clarity_display_name(water_clarity),
                    'description': WATER_CLARITY_DESCRIPTIONS[water_clarity],
                    'guidance': clarity_guidance  # Raw strings without bullets/emojis
                })
            
            # ===== MAINTENANCE TIPS =====
            if slam_context == 'normal':
                maintenance_tips = [
                    "Test water weekly",
                    "Brush walls weekly",
                    "Clean filter as needed",
                    "Enjoy your pool!"
                ]
                
                if CYA is not None:
                    if CYA == 0:
                        maintenance_tips.insert(1, "Maintain chlorine 1-3 ppm (no CYA)")
                    elif CYA < 30:
                        maintenance_low = CYA * 0.075
                        maintenance_high = CYA * 0.15
                        maintenance_tips.insert(1, f"Maintain chlorine {maintenance_low:.1f}-{maintenance_high:.1f} ppm")
                        maintenance_tips.insert(2, "Shock level limited to 10 ppm due to low CYA")
                    else:
                        maintenance_low = CYA * 0.075
                        maintenance_high = CYA * 0.15
                        maintenance_tips.insert(1, f"Maintain chlorine {maintenance_low:.1f}-{maintenance_high:.1f} ppm")
                else:
                    maintenance_tips.insert(1, UNKNOWN_CYA['WARNING'])
                    maintenance_tips.insert(2, f"Use safe range: {UNKNOWN_CYA['SAFE_MAINTENANCE_MIN']}-{UNKNOWN_CYA['SAFE_MAINTENANCE_MAX']} ppm")
            
            elif slam_context == 'post_slam':
                maintenance_tips = [
                    "Test daily until stable",
                    "Brush daily to suspend dead algae",
                    "Clean filter when pressure rises 25%",
                    "Patience - clearing takes 3-7 days"
                ]
            
            elif slam_context == 'post_slam_final':
                maintenance_tips = [
                    "Maintain chlorine at maintenance levels",
                    "Continue filtering - water will clear",
                    "Backwash filter as needed",
                    "You can gradually reduce pump runtime"
                ]
            
            else:  # Pre-SLAM or During SLAM
                maintenance_tips = [
                    "Test chlorine every 2-4 hours",
                    "Brush pool daily",
                    "Run pump 24/7",
                    "Clean filter when pressure rises 25%"
                ]
            
            if maintenance_tips:
                builder.add_maintenance_tips(maintenance_tips)
            
            # Add footer
            builder.add_footer()
            
            # Build and return the final string
            result = builder.build()
            return result
        
        except Exception as e:
            print(f"!!! EXCEPTION IN adjust_pool: {repr(e)}")
            traceback.print_exc()
            return f"Error in calculation: {str(e)}"
    
    # ==============================
    # Calculation Entry Point
    # ==============================
    
    def calculate(self):
        try:
            volume_str = self.entry_volume.get().strip() or str(self.app_state.config['pool_volume'])
            try:
                volume = int(volume_str)
            except ValueError:
                messagebox.showerror("Error", "Pool volume must be a whole number (no decimals or letters).")
                return
            if volume <= 0:
                messagebox.showerror("Error", "Pool volume must be greater than 0.")
                return

            def safe_float_get(entry, field_name, default=None, min_val=None, max_val=None):
                val_str = entry.get().strip()
                if not val_str:
                    return default
                try:
                    val = float(val_str)
                    if min_val is not None and val < min_val:
                        messagebox.showerror("Error", f"{field_name} must be at least {min_val}.")
                        raise ValueError
                    if max_val is not None and val > max_val:
                        messagebox.showerror("Error", f"{field_name} cannot exceed {max_val}.")
                        raise ValueError
                    return val
                except ValueError:
                    messagebox.showerror("Error", f"Invalid {field_name}: '{val_str}'")
                    raise

            pH = safe_float_get(self.entry_pH, "pH", None, 0, 14)
            TA = safe_float_get(self.entry_TA, "Total Alkalinity", None, 0, 500)
            Cl = safe_float_get(self.entry_chlorine, "Chlorine", None, 0, 100)
            CYA = safe_float_get(self.entry_cya, "CYA", None, 0, 300)
            CH = safe_float_get(self.entry_calcium, "Calcium Hardness", None, 0, 1000)

            hcl = safe_float_get(self.entry_hcl, "HCl percentage", self.app_state.config['hcl_percent'], 0, 100) or self.app_state.config['hcl_percent']
            bleach = safe_float_get(self.entry_bleach, "bleach percentage", self.app_state.config['bleach_percent'], 0, 100) or self.app_state.config['bleach_percent']

            cal_hypo_from_config = self.app_state.config.get('cal_hypo_percent', 65.0)
            cal_hypo_percent = cal_hypo_from_config

            val_str = self.entry_cal_hypo.get().strip()
            if val_str:
                try:
                    cal_hypo_percent = float(val_str)
                except ValueError:
                    messagebox.showwarning(
                        "Warning",
                        f"Invalid Cal-Hypo percentage '{val_str}' — using saved value {cal_hypo_from_config}%"
                    )

            pump = None
            if self.entry_pump_flow.get().strip():
                try:
                    pump = float(self.entry_pump_flow.get())
                    if pump < 0:
                        messagebox.showerror("Error", "Pump flow rate cannot be negative.")
                        return
                    if pump == 0:
                        pump = None
                except ValueError:
                    messagebox.showwarning("Warning", "Invalid pump flow - ignoring")

            input_warnings = self.validate_inputs(volume, hcl, bleach, pump, cal_hypo_percent)
            if input_warnings:
                messagebox.showwarning("Check Your Inputs", "\n".join(input_warnings))

            water_clarity_display = self.clarity_var.get()
            water_clarity = get_clarity_internal_key(water_clarity_display)
            is_slam_mode = self.slam_mode_var.get()
            overnight_test = self.overnight_test_var.get() if self.overnight_test_var else "not_tested"
            
            # ===== OVERNIGHT TEST RESET LOGIC =====
            original_overnight = overnight_test
            reset_reason = None
            
            # Rule 1: If SLAM mode is off, overnight test should be "not_tested"
            if not is_slam_mode and overnight_test != "not_tested":
                overnight_test = "not_tested"
                reset_reason = "SLAM mode is off"
            
            # Rule 2: If algae is present, overnight test cannot be "passed"
            if water_clarity in ["green_algae", "black_algae"] and overnight_test == "passed":
                overnight_test = "not_tested"
                reset_reason = "Algae present (can't have passed overnight test)"
            
            # Rule 3: If water is clear and SLAM is off, overnight test should be "not_tested"
            if water_clarity == "crystal_clear" and not is_slam_mode and overnight_test != "not_tested":
                overnight_test = "not_tested"
                reset_reason = "Normal mode with clear water"
            
            # Update UI if we reset the value
            if original_overnight != overnight_test:
                if self.overnight_test_var:
                    self.overnight_test_var.set(overnight_test)

            results = self.adjust_pool(
                {'pH': pH, 'alkalinity': TA, 'chlorine': Cl, 'cya': CYA, 'calcium': CH},
                {
                    'pool_volume_liters': volume,
                    'hcl_percent': hcl,
                    'bleach_percent': bleach,
                    'cal_hypo_percent': cal_hypo_percent,
                    'pump_flow_rate': pump
                },
                water_clarity=water_clarity,
                is_slam_mode=is_slam_mode,
                overnight_test=overnight_test
            )

            if not results:
                messagebox.showinfo("Recommendations", "All parameters in optimal range.")
            else:
                self.show_scrollable_results("Pool Chemistry Recommendations", results)

            # Update config with current UI state
            self.app_state.config.update({
                'pool_volume': volume,
                'hcl_percent': hcl,
                'bleach_percent': bleach,
                'cal_hypo_percent': cal_hypo_percent,
                'pump_flow_rate': pump,
                'water_clarity': water_clarity,
                'overnight_test': overnight_test,  # Use the potentially reset value
                'previous_slam_mode': is_slam_mode,
                'previous_water_clarity': water_clarity
            })
            save_config(self.app_state.config, self.app_state.config_file, self)

            # Save to history
            self.save_to_history(
                volume=volume,
                hcl=hcl,
                bleach=bleach,
                cal_hypo_percent=cal_hypo_percent,
                pump=pump,
                water_clarity_display=water_clarity_display,
                is_slam_mode=is_slam_mode,
                overnight_test=overnight_test,  # Use the potentially reset value
                pH=pH,
                TA=TA,
                Cl=Cl,
                CYA=CYA,
                CH=CH,
                results=results
            )

        except Exception as e:
            messagebox.showerror("Error", f"Calculation failed:\n{str(e)}")
        
    def save_to_history(self, volume, hcl, bleach, cal_hypo_percent, pump, water_clarity_display,
                    is_slam_mode, overnight_test, pH, TA, Cl, CYA, CH, results):
        """
        Append the full guidance report to history file (no duplicate summary).
        """
        history_path_str = self.app_state.config.get('history_path')
        if not history_path_str:
            return  # silently skip if no path

        history_file = Path(history_path_str)
        
        try:
            history_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Read existing content (if any)
            existing = history_file.read_text(encoding="utf-8") if history_file.exists() else ""
            
            # Temp file for safe write
            temp_file = history_file.with_suffix(".tmp")
            
            with temp_file.open("w", encoding="utf-8") as f:
                # Only a minimal separator + timestamp (no duplicate parameters)
                f.write("=" * 50 + "\n")
                f.write(f"Calculation: {datetime.now():%Y-%m-%d %H:%M}\n")
                f.write("=" * 50 + "\n\n")
                
                # === The clean, full report ===
                if results:
                    if isinstance(results, str):
                        f.write(results + "\n\n")
                    else:
                        f.write("\n".join(str(r) for r in results) + "\n\n")
                
                # Append previous entries
                f.write(existing)
            
            # Atomic replace
            temp_file.replace(history_file)
            
        except Exception as e:
            # Optional: log silently or warn user
            pass
        
    def validate_inputs(self, volume, hcl_percent, bleach_percent, pump_flow_rate, cal_hypo_percent=65.0):
        """Validate input values."""
        warnings = []
        if volume < 1000 or volume > 200000:
            warnings.append("Warning: Pool volume seems unusual")
        if hcl_percent < 10 or hcl_percent > 35:
            warnings.append("Warning: HCl concentration should be 10-35%")
        if bleach_percent < 5 or bleach_percent > 15:
            warnings.append("Warning: Bleach concentration should be 5-15%")
        if cal_hypo_percent < 50 or cal_hypo_percent > 80:
            warnings.append(f"Warning: Cal-Hypo concentration ({cal_hypo_percent}%) should be 50-80%")
        if pump_flow_rate is not None and (pump_flow_rate < 1000 or pump_flow_rate > 50000):
            warnings.append(f"Warning: Pump flow rate ({pump_flow_rate} L/h) seems unusual. Typical is 1000-50000 L/h")
        return warnings
    
    def view_history(self):
        """View history file."""
        path = self.app_state.config.get('history_path')
        if not path or not os.path.exists(path):
            messagebox.showinfo("History", "No history file found.")
            return
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            win = tk.Toplevel(self.root)
            win.title("History")
            win.geometry("700x500")
            
            history_text = ScrolledText(win, wrap="word")
            history_text.insert(tk.END, content)
            history_text.pack(fill="both", expand=True)
            
            tk.Label(win, text=f"File: {path}", fg="gray", font=("Arial", 8)).pack(side="bottom", anchor="w")
        except Exception as e:
            messagebox.showerror("Error", f"Cannot read history: {e}")
    
    def load_config(self):
        """Load configuration from file into app_state."""
        exe_dir = self.get_exe_dir()
        config_file = os.path.join(exe_dir, "pool_config.txt")
        default_history = os.path.join(exe_dir, "pool_history.txt")
        
        config = {
            'history_path': default_history,
            'pool_volume': 7250,
            'hcl_percent': 31.45,
            'bleach_percent': 12.5,
            'cal_hypo_percent': 65.0,
            'pump_flow_rate': None,
            'water_clarity': 'crystal_clear',
            'overnight_test': 'not_tested',
            'previous_water_clarity': 'crystal_clear',
            'previous_slam_mode': False,
            'last_seen_date': None
        }
        
        # Create default config if it doesn't exist
        if not os.path.exists(config_file):
            # Save with default values (no app_instance needed for initial creation)
            self._save_config_to_file(config, config_file)
        
        # Load existing config if it exists
        if os.path.exists(config_file):
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if '=' not in line:
                            continue
                        k, v = line.strip().split('=', 1)
                        v = v.strip()
                        
                        if k == 'history_path' and v.lower() != 'none':
                            config[k] = v or default_history
                        elif k == 'pool_volume':
                            if v.isdigit():
                                config[k] = int(v)
                        elif k in ['hcl_percent', 'bleach_percent', 'cal_hypo_percent', 'pump_flow_rate']:
                            if v and v.lower() != 'none':
                                try:
                                    config[k] = float(v)
                                except ValueError:
                                    pass  # Keep default on error
                            else:
                                config[k] = None if k == 'pump_flow_rate' else config[k]
                        elif k == 'water_clarity':
                            if v in WATER_CLARITY_OPTIONS:
                                config[k] = v
                            else:
                                # Try to convert from display name to internal key
                                internal_key = None
                                for clarity in WATER_CLARITY_OPTIONS:
                                    if get_clarity_display_name(clarity) == v:
                                        internal_key = clarity
                                        break
                                config[k] = internal_key or 'crystal_clear'
                        elif k == 'overnight_test':
                            if v in ['not_tested', 'passed', 'failed']:
                                config[k] = v
                        elif k == 'previous_water_clarity':
                            if v in WATER_CLARITY_OPTIONS:
                                config['previous_water_clarity'] = v
                        elif k == 'previous_slam_mode':
                            config['previous_slam_mode'] = v.lower() == 'true' if v else False
                        elif k == 'last_seen_date':
                            config['last_seen_date'] = v
            except Exception as e:
                # Continue with defaults on error
                pass
        
        # Ensure history path is writable
        history_dir = os.path.dirname(config['history_path']) or exe_dir
        if not os.access(history_dir, os.W_OK):
            config['history_path'] = os.path.join(os.path.expanduser("~"), "Desktop", "pool_history.txt")
        
        # Store in app_state
        self.app_state.config = config
        self.app_state.config_file = config_file

    def _save_config_to_file(self, config, path):
        """Internal method to save config to file without requiring app_instance."""
        try:
            with open(path, "w", encoding="utf-8") as f:
                for k, v in config.items():
                    if v is None or v == '':
                        v = ''
                    f.write(f"{k}={v}\n")
        except Exception as e:
            print(f"DEBUG: Error saving config: {e}")
    
    def get_exe_dir(self):
        """Get directory of executable or script."""
        try:
            if getattr(sys, 'frozen', False):
                return os.path.dirname(sys.executable)
            return os.path.dirname(os.path.abspath(__file__))
        except Exception:
            return os.path.dirname(os.path.abspath(__file__))
        
    def show_scrollable_results(self, title, text):
        """Show results in a scrollable window with proper formatting."""
        
        # Create a top-level window
        result_window = tk.Toplevel(self.root)
        result_window.title(title)
        result_window.geometry("750x600")
        result_window.transient(self.root)
        result_window.grab_set()

        # Center the window
        result_window.update_idletasks()
        width = result_window.winfo_width()
        height = result_window.winfo_height()
        x = (result_window.winfo_screenwidth() // 2) - (width // 2)
        y = (result_window.winfo_screenheight() // 2) - (height // 2)
        result_window.geometry(f'{width}x{height}+{x}+{y}')
        
        # Create a frame for the text and scrollbar
        frame = tk.Frame(result_window)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Add scrollbars
        y_scrollbar = tk.Scrollbar(frame)
        y_scrollbar.pack(side="right", fill="y")
        
        x_scrollbar = tk.Scrollbar(frame, orient="horizontal")
        x_scrollbar.pack(side="bottom", fill="x")
        
        # Add a text widget
        text_widget = tk.Text(frame, wrap="none",
                            yscrollcommand=y_scrollbar.set,
                            xscrollcommand=x_scrollbar.set,
                            font=("Courier New", 10),
                            bg="white", 
                            relief="sunken", 
                            borderwidth=2)
        text_widget.pack(side="left", fill="both", expand=True)
        
        # Configure scrollbars
        y_scrollbar.config(command=text_widget.yview)
        x_scrollbar.config(command=text_widget.xview)
        
        # Clear and insert the text
        text_widget.delete("1.0", tk.END)
        text_widget.insert("1.0", text)
        
        text_widget.config(state="disabled")
        
        # Add buttons
        button_frame = tk.Frame(result_window)
        button_frame.pack(fill="x", pady=(0, 10))
        
        def copy_to_clipboard():
            result_window.clipboard_clear()
            result_window.clipboard_append(text)
            result_window.update()
            original_text = copy_btn.cget("text")
            copy_btn.config(text="✅ Copied!", bg="#4CAF50")
            result_window.after(1500, lambda: copy_btn.config(text=original_text, bg="#2196F3"))
        
        copy_btn = tk.Button(button_frame, text="📋 Copy to Clipboard", 
                            command=copy_to_clipboard,
                            bg="#2196F3", fg="white", font=("Arial", 9, "bold"),
                            width=15)
        copy_btn.pack(side="left", padx=(20, 10))
        
        tk.Button(button_frame, text="OK", command=result_window.destroy,
                bg="#4CAF50", fg="white", font=("Arial", 10, "bold"),
                width=10).pack(side="right", padx=(10, 20))  
        
# ==============================
# Config Save Function (kept separate as it's a simple utility)
# ==============================
def save_config(config, path, app_instance=None):
    """Save configuration to file."""
    try:
        # If app_instance provided, update with current UI state
        if app_instance and hasattr(app_instance, 'clarity_var') and app_instance.clarity_var:
            try:
                curr_clarity = get_clarity_internal_key(app_instance.clarity_var.get())
                curr_slam = app_instance.slam_mode_var.get() if hasattr(app_instance, 'slam_mode_var') else False
                config['previous_water_clarity'] = curr_clarity
                config['previous_slam_mode'] = str(curr_slam)
                config['last_seen_date'] = datetime.now().strftime('%Y-%m-%d')

                for field, key in [
                    (getattr(app_instance, 'entry_hcl', None),    'hcl_percent'),
                    (getattr(app_instance, 'entry_bleach', None), 'bleach_percent'),
                    (getattr(app_instance, 'entry_cal_hypo', None), 'cal_hypo_percent'),
                ]:
                    if field is not None:
                        val_str = field.get().strip()
                        if val_str:
                            try:
                                config[key] = float(val_str)
                            except ValueError:
                                pass  # Keep old value on error

            except Exception as e:
                pass  # Silently continue
        
        # Write to file
        with open(path, "w", encoding="utf-8") as f:
            for k, v in config.items():
                if v is None or v == '':
                    v = ''
                f.write(f"{k}={v}\n")
                
    except Exception as e:
        if app_instance:
            messagebox.showwarning("Warning", f"Could not save config: {e}")

# ==============================
# Main Entry Point
# ==============================
if __name__ == "__main__":
    root = tk.Tk()

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        messagebox.showerror("Unexpected Error", f"An unexpected error occurred:\n{exc_value}")

    sys.excepthook = handle_exception

    app = PoolChemistryApp(root)
    root.mainloop()