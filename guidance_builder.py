"""
Guidance Builder V30 for Pool Chemistry Assistant
Creates structured, professional output with consistent section ordering
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime
import traceback
import sys


class OutputSection(Enum):
    """Enum defining all possible output sections in order of appearance"""
    HEADER = "header"
    PARAMETERS = "parameters"
    MODE = "mode"
    CHEMISTRY_ANALYSIS = "chemistry_analysis"
    SLAM_DOSES = "slam_doses"
    SLAM_MAINTENANCE = "slam_maintenance"
    KEY_MILESTONE = "key_milestone"
    DOSEAGES = "doseages"
    PUMP_GUIDANCE = "pump_guidance"
    WATER_CLARITY = "water_clarity"
    MAINTENANCE_TIPS = "maintenance_tips"
    FOOTER = "footer"


class GuidanceBuilder:
    """
    Builds structured guidance output with consistent section ordering.
    """
     
    SECTION_ORDER = [
        OutputSection.HEADER,
        OutputSection.PARAMETERS,
        OutputSection.MODE,
        OutputSection.CHEMISTRY_ANALYSIS,
        OutputSection.SLAM_DOSES,
        OutputSection.SLAM_MAINTENANCE,
        OutputSection.KEY_MILESTONE,
        OutputSection.DOSEAGES,
        OutputSection.PUMP_GUIDANCE,
        OutputSection.WATER_CLARITY,
        OutputSection.MAINTENANCE_TIPS,
        OutputSection.FOOTER,
    ]
    
    SECTION_TITLES = {
        OutputSection.HEADER: "POOL CHEMISTRY ASSISTANT",
        OutputSection.PARAMETERS: "POOL PARAMETERS",
        OutputSection.MODE: "OPERATING MODE",
        OutputSection.CHEMISTRY_ANALYSIS: "CHEMISTRY ANALYSIS",
        OutputSection.SLAM_DOSES: "SLAM CHLORINE DOSES",
        OutputSection.SLAM_MAINTENANCE: "SLAM MAINTENANCE",
        OutputSection.KEY_MILESTONE: "KEY MILESTONE",
        OutputSection.DOSEAGES: "CHEMICAL DOSES",
        OutputSection.PUMP_GUIDANCE: "PUMP GUIDANCE",
        OutputSection.WATER_CLARITY: "WATER CLARITY",
        OutputSection.MAINTENANCE_TIPS: "MAINTENANCE TIPS",
        OutputSection.FOOTER: "END OF REPORT",
    }
    
    SECTION_EMOJIS = {
        OutputSection.HEADER: "",
        OutputSection.PARAMETERS: "",
        OutputSection.MODE: "⚙️",
        OutputSection.CHEMISTRY_ANALYSIS: "📊",
        OutputSection.SLAM_DOSES: "⚡",
        OutputSection.SLAM_MAINTENANCE: "🔧",
        OutputSection.KEY_MILESTONE: "🎯",
        OutputSection.DOSEAGES: "💧",
        OutputSection.PUMP_GUIDANCE: "🔄",
        OutputSection.WATER_CLARITY: "💎",
        OutputSection.MAINTENANCE_TIPS: "✅",
        OutputSection.FOOTER: "",
    }
    
    def __init__(self):
        """Initialize an empty builder."""
        self.sections: Dict[OutputSection, List[str]] = {}
        self.has_content: Dict[OutputSection, bool] = {}
        
        for section in OutputSection:
            self.sections[section] = []
            self.has_content[section] = False

    def safe_traceback(self) -> None:
        """Safely print the current exception's traceback."""
        try:
            traceback.print_exc(file=sys.stderr)
        except UnicodeEncodeError:
            exc_type, exc_value, exc_tb = sys.exc_info()
            if exc_tb is None:
                print(f"ERROR (no traceback available): {exc_value}", file=sys.stderr)
                return
            
            lines = traceback.format_exception(exc_type, exc_value, exc_tb)
            for line in lines:
                safe_line = line.encode('ascii', 'replace').decode('ascii')
                print(safe_line, end='', file=sys.stderr)
    
    def _add_line(self, section: OutputSection, line: str):
        """Add a line to a section."""
        if line and line.strip():
            self.sections[section].append(line)
            self.has_content[section] = True
    
    def _add_lines(self, section: OutputSection, lines: List[str]):
        """Add multiple lines to a section."""
        for line in lines:
            if line and line.strip():
                self.sections[section].append(line)
                self.has_content[section] = True
    
    def add_header(self, title: str = "POOL CHEMISTRY ASSISTANT"):
        """Add the report header."""
        lines = [
            f"{'='*47}",
            f"{self.SECTION_EMOJIS[OutputSection.HEADER]} {title}",
            f"{'='*47}"
        ]
        self._add_lines(OutputSection.HEADER, lines)
        return self
    
    def add_parameters(self, volume: Optional[float] = None, pump: Optional[float] = None, 
                       slam_mode: Optional[str] = None, clarity: Optional[str] = None, 
                       overnight_test: Optional[str] = None):
        """Add pool parameters section."""
        param_parts = []
        
        if volume is not None:
            param_parts.append(f"Volume={volume:.0f}L")
        if pump is not None and pump > 0:
            param_parts.append(f"Pump={pump:.0f}L/h")
        if slam_mode is not None:
            param_parts.append(f"SLAM={slam_mode}")
        if clarity is not None:
            param_parts.append(f"Clarity={clarity}")
        if overnight_test is not None:
            overnight_display = overnight_test.replace('_', ' ').title()
            param_parts.append(f"Overnight={overnight_display}")
        
        if param_parts:
            lines = [
                f"Date: {datetime.now():%Y-%m-%d %H:%M}",
                f"Parameters: {', '.join(param_parts)}"
            ]
            self._add_lines(OutputSection.PARAMETERS, lines)
        
        return self
    
    def add_mode(self, mode: str):
        """Add operating mode section."""
        mode_display = {
            'pre_slam': "PRE-SLAM ASSESSMENT",
            'during_slam': "ACTIVE SLAM IN PROGRESS",
            'post_slam': "POST-SLAM RECOVERY",
            'post_slam_final': "POST-SLAM FINAL STAGE",
            'normal': "MAINTENANCE MODE"
        }.get(mode, mode.upper())
        
        lines = [
            f"[MODE] {mode_display}",
            f"{'─'*47}"
        ]
        self._add_lines(OutputSection.MODE, lines)
        return self
    
    def add_chemistry_analysis(self, readings: Dict[str, Optional[float]], 
                                statuses: Dict[str, str]):
        """Add chemistry analysis section with readings and statuses."""
        lines = [f"[CHEMISTRY ANALYSIS] {self.SECTION_EMOJIS[OutputSection.CHEMISTRY_ANALYSIS]}"]
        
        param_order = ['pH', 'TA', 'Cl', 'CYA', 'CH']
        param_names = {
            'pH': 'pH',
            'TA': 'TA',
            'Cl': 'Cl',
            'CYA': 'CYA',
            'CH': 'CH'
        }
        
        for param in param_order:
            value = readings.get(param)
            status = statuses.get(param, "")
            
            if value is not None:
                if param == 'pH':
                    lines.append(f"   • {param_names[param]}: {value:.2f} ({status})")
                elif param == 'Cl':
                    lines.append(f"   • {param_names[param]}: {value:.1f} ppm ({status})")
                else:
                    lines.append(f"   • {param_names[param]}: {value:.0f} ppm ({status})")
            else:
                lines.append(f"   • {param_names[param]}: Not tested")
        
        self._add_lines(OutputSection.CHEMISTRY_ANALYSIS, lines)
        return self
    
    def add_slam_doses(self, dose_data: Dict[str, Any]):
        """
        Add SLAM chlorine doses with standardized formatting.
        
        Expected format:
        {
            'target_fc': float,
            'current_fc': float,
            'liquid': {'amount': float, 'unit': str, 'percentage': float},
            'cal_hypo': {'amount': float, 'unit': str, 'percentage': float},
            'is_slam': bool,
            'split_info': {
                'needed': bool,
                'doses': int,
                'per_dose_liquid': float,
                'per_dose_cal_hypo': float,
                'interval': int
            } (optional),
            'notes': List[str],
            'warnings': List[str]
        }
        """
        try:
            lines = [
                f"[SLAM DOSES] {self.SECTION_EMOJIS[OutputSection.SLAM_DOSES]}",
                f"{'─'*47}",
                f"   Raise FC to {dose_data['target_fc']:.1f} ppm:",
                f"     • Add ≈ {dose_data['liquid']['amount']:.0f} {dose_data['liquid']['unit']} of {dose_data['liquid']['percentage']}% liquid chlorine",
                f"     • OR add ≈ {dose_data['cal_hypo']['amount']:.0f} {dose_data['cal_hypo']['unit']} of {dose_data['cal_hypo']['percentage']}% calcium hypochlorite"
            ]
            
            # Add split dosing info if needed
            if dose_data.get('split_info', {}).get('needed', False):
                split = dose_data['split_info']
                lines.append("")
                lines.append(f"   Large raise required → split into ≈ {split['doses']} doses:")
                lines.append(f"     • ≈ {split['per_dose_liquid']:.0f} ml liquid chlorine   OR   ≈ {split['per_dose_cal_hypo']:.0f} g Cal-Hypo per dose")
                lines.append(f"     • Wait {split['interval']}–6 hours, re-test FC, then add next dose if needed")
            
            # Add notes
            if dose_data.get('notes'):
                lines.append("")
                lines.append("   Notes on your options:")
                for note in dose_data['notes']:
                    lines.append(f"     • {note}")
            
            # Add warnings
            if dose_data.get('warnings'):
                for warning in dose_data['warnings']:
                    lines.append(f"   ⚠️ {warning}")
            
            self._add_lines(OutputSection.SLAM_DOSES, lines)
        except Exception as e:
            print(f"ERROR in add_slam_doses: {e}", file=sys.stderr)
            self.safe_traceback()
        return self
    
    def add_slam_maintenance(self, items: List[str]):
        """Add SLAM maintenance instructions."""
        try:
            if items:
                lines = [
                    f"[SLAM MAINTENANCE] {self.SECTION_EMOJIS[OutputSection.SLAM_MAINTENANCE]}",
                    f"{'─'*47}"
                ]
                for item in items:
                    lines.append(f"   • {item}")
                self._add_lines(OutputSection.SLAM_MAINTENANCE, lines)
        except Exception as e:
            print(f"ERROR in add_slam_maintenance: {e}", file=sys.stderr)
            self.safe_traceback()
        return self
    
    def add_key_milestone(self, title: str, items: List[str]):
        """Add key milestone section."""
        try:
            if items:
                lines = [
                    f"[{title}] {self.SECTION_EMOJIS[OutputSection.KEY_MILESTONE]}",
                    f"{'─'*47}"
                ]
                for item in items:
                    lines.append(f"   • {item}")
                self._add_lines(OutputSection.KEY_MILESTONE, lines)
        except Exception as e:
            print(f"ERROR in add_key_milestone: {e}", file=sys.stderr)
            self.safe_traceback()
        return self
    
    def add_doseages(self, dose_data: List[Dict[str, Any]]):
        """
        Add regular (non-SLAM) chemical doses with standardized formatting.
        
        Expected format for each dose:
        {
            'type': str,  # 'ph', 'ta', 'cya', 'calcium', 'protocol'
            'action': str,  # The main action text
            'details': List[str],  # Bullet points or numbered steps
            'warnings': List[str]
        }
        """
        try:
            if not dose_data:
                return
                
            lines = [
                f"[CHEMICAL DOSES] {self.SECTION_EMOJIS[OutputSection.DOSEAGES]}",
                f"{'─'*47}"
            ]
            
            for dose in dose_data:
                if dose.get('action'):
                    lines.append(f"   {dose['action']}")
                
                if dose.get('details'):
                    for i, detail in enumerate(dose['details']):
                        # Use numbers for sequential steps, bullets for lists
                        if len(dose['details']) > 1 and i < len(dose['details']):
                            lines.append(f"     {i+1}. {detail}")
                        else:
                            lines.append(f"     • {detail}")
                
                if dose.get('warnings'):
                    for warning in dose['warnings']:
                        lines.append(f"   ⚠️ {warning}")
                
                lines.append("")  # Blank line between doses
            
            self._add_lines(OutputSection.DOSEAGES, lines)
        except Exception as e:
            print(f"ERROR in add_doseages: {e}", file=sys.stderr)
            self.safe_traceback()
        return self
    
    def add_pump_guidance(self, guidance_data: Dict[str, Any]):
        """
        Add pump guidance section with standardized formatting.
        
        Expected format:
        {
            'has_pump_data': bool,
            'turnover_hours': float (optional),
            'guidance': List[str]  # Raw guidance lines without bullets
        }
        """
        try:
            if not guidance_data.get('guidance'):
                return
                
            lines = [
                f"[PUMP GUIDANCE] {self.SECTION_EMOJIS[OutputSection.PUMP_GUIDANCE]}",
                f"{'─'*47}"
            ]
            
            for line in guidance_data['guidance']:
                lines.append(f"   • {line}")
            
            self._add_lines(OutputSection.PUMP_GUIDANCE, lines)
        except Exception as e:
            print(f"ERROR in add_pump_guidance: {e}", file=sys.stderr)
            self.safe_traceback()
        return self
    
    def add_water_clarity(self, clarity_data: Dict[str, Any]):
        """
        Add water clarity section with standardized formatting.
        
        Expected format:
        {
            'status': str,
            'description': str,
            'guidance': List[str]
        }
        """
        try:
            lines = [
                f"[WATER CLARITY] {self.SECTION_EMOJIS[OutputSection.WATER_CLARITY]}",
                f"{'─'*47}",
                f"   • Status: {clarity_data['status']}",
                f"   • {clarity_data['description']}"
            ]
            
            for line in clarity_data.get('guidance', []):
                lines.append(f"   • {line}")
            
            self._add_lines(OutputSection.WATER_CLARITY, lines)
        except Exception as e:
            print(f"ERROR in add_water_clarity: {e}", file=sys.stderr)
            self.safe_traceback()
        return self
    
    def add_maintenance_tips(self, tips: List[str]):
        """Add general maintenance tips."""
        try:
            if tips:
                lines = [
                    f"[MAINTENANCE TIPS] {self.SECTION_EMOJIS[OutputSection.MAINTENANCE_TIPS]}",
                    f"{'─'*47}"
                ]
                for tip in tips:
                    lines.append(f"   • {tip}")
                self._add_lines(OutputSection.MAINTENANCE_TIPS, lines)
        except Exception as e:
            print(f"ERROR in add_maintenance_tips: {e}", file=sys.stderr)
            self.safe_traceback()
        return self
    
    def add_footer(self):
        """Add report footer."""
        try:
            lines = [
                f"{'='*47}",
                f"{self.SECTION_EMOJIS[OutputSection.FOOTER]} {self.SECTION_TITLES[OutputSection.FOOTER]}",
                f"{'='*47}"
            ]
            self._add_lines(OutputSection.FOOTER, lines)
        except Exception as e:
            print(f"ERROR in add_footer: {e}", file=sys.stderr)
            self.safe_traceback()
        return self
    
    def build(self) -> str:
        """Build the complete output string with only sections that have content."""
        output_lines = []
        
        for section in self.SECTION_ORDER:
            if self.has_content.get(section, False):
                output_lines.extend(self.sections[section])
                if section != self.SECTION_ORDER[-1]:
                    output_lines.append("")
        
        return "\n".join(output_lines)
    
    def clear(self):
        """Clear all sections (reuse builder)."""
        for section in OutputSection:
            self.sections[section] = []
            self.has_content[section] = False
        return self