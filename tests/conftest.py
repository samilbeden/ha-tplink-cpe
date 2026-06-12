"""Make the HA-free parser module importable without installing Home Assistant."""
import pathlib
import sys

PKG = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "tplink_cpe"
sys.path.insert(0, str(PKG))
