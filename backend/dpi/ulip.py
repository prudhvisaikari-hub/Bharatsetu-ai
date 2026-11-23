"""ULIP Adapter (Unified Logistics Interface Platform / NLDS API Specification).
Tracks multi-modal consignment transit via FASTag toll logs, Vahan vehicle fitness, and Sarathi.
"""
import datetime as dt
from typing import Dict, Any, Optional
from .base import DPIAdapter

class ULIPAdapter(DPIAdapter):
    def __init__(self, is_mock: bool = True):
        super().__init__("ULIP", is_mock=is_mock)

    def track_consignment(
        self,
        vehicle_number: str = "MP-09-GH-8219",
        consignment_id: Optional[str] = None,
        msme_id: str = "demo"
    ) -> Dict[str, Any]:
        self.record_consent(
            msme_id=msme_id,
            purpose="In-Transit Raw Material / Delivery Tracking via FASTag & Vahan",
            scope="Vehicle Location and Toll Plaza Timestamp Logs",
            expiry_days=7,
            extra_details={"vehicle_number": vehicle_number}
        )
        if self.is_mock:
            now = dt.datetime.now()
            return {
                "status": "IN_TRANSIT",
                "vehicle_number": vehicle_number,
                "vahan_status": {
                    "rc_status": "ACTIVE",
                    "fitness_valid_upto": "2027-05-12",
                    "insurance_valid_upto": "2027-03-10",
                    "emission_puc_valid": True
                },
                "fastag_toll_trail": [
                    {
                        "plaza": "Raipur Bypass Toll Plaza",
                        "time": (now - dt.timedelta(hours=14)).strftime("%Y-%m-%d %H:%M:%S"),
                        "direction": "Outward"
                    },
                    {
                        "plaza": "Nagpur-Betul Expressway Toll",
                        "time": (now - dt.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"),
                        "direction": "Transit"
                    },
                    {
                        "plaza": "Indore-Pithampur Tollway Plaza",
                        "time": (now - dt.timedelta(minutes=45)).strftime("%Y-%m-%d %H:%M:%S"),
                        "direction": "Destination Inward"
                    }
                ],
                "current_location_estimate": "Sector 3 Industrial Area, Pithampur",
                "estimated_delivery_time": (now + dt.timedelta(minutes=30)).strftime("%H:%M IST"),
                "simulated": True
            }
        # Real-implementation stub for ULIP gateway (POST /ulip/v1.0/FASTAG/01)
        raise NotImplementedError("Real ULIP integration requires approved DPI logistics API credentials")
