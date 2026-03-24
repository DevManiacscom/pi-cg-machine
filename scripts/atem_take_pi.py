#!/usr/bin/env python3
import os
import sys
import time

from PyATEMMax import ATEMMax


def main() -> int:
    atem_ip = os.getenv("ATEM_IP")
    if not atem_ip:
        print("ATEM_IP is not set", file=sys.stderr)
        return 1

    raw_input = os.getenv("ATEM_PI_INPUT")
    if not raw_input:
        print("ATEM_PI_INPUT is not set", file=sys.stderr)
        return 1

    try:
        atem_pi_input = int(raw_input)
    except ValueError:
        print("ATEM_PI_INPUT must be an integer", file=sys.stderr)
        return 1

    if atem_pi_input <= 0:
        print("ATEM_PI_INPUT must be greater than 0", file=sys.stderr)
        return 1

    atem = ATEMMax()

    try:
        atem.connect(atem_ip)

        # Give the connection a moment to initialize.
        time.sleep(2)

        # Use the primary M/E bus (index 0).
        atem.setProgramInputVideoSource(0, atem_pi_input)

        time.sleep(1)
        return 0
    finally:
        try:
            atem.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())