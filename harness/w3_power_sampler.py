#!/usr/bin/env python3
"""Furnace bench W3: 1 Hz rocm-smi power/temp/clock sampler.
Writes CSV: epoch,iso,power_w,temp_edge_c,sclk_mhz,mclk_mhz
Runs until SIGTERM. Output path from argv[1].
"""
import re, signal, subprocess, sys, time

OUT = sys.argv[1]
stop = False

def _h(sig, frm):
    global stop
    stop = True
signal.signal(signal.SIGTERM, _h)
signal.signal(signal.SIGINT, _h)

f = open(OUT, "w", buffering=1)
f.write("epoch,iso,power_w,temp_edge_c,sclk_mhz,mclk_mhz\n")
while not stop:
    t0 = time.time()
    power = temp = sclk = mclk = ""
    try:
        out = subprocess.run(["rocm-smi", "--showpower", "--showtemp", "--showclocks"],
                             capture_output=True, text=True, timeout=5).stdout
        m = re.search(r"Current Socket Graphics Package Power \(W\):\s*([\d.]+)", out)
        if m: power = m.group(1)
        m = re.search(r"Temperature \(Sensor edge\) \(C\):\s*([\d.]+)", out)
        if m: temp = m.group(1)
        m = re.search(r"sclk clock level:\s*\d+:\s*\((\d+)Mhz\)", out)
        if m: sclk = m.group(1)
        m = re.search(r"mclk clock level:\s*\d+:\s*\((\d+)Mhz\)", out)
        if m: mclk = m.group(1)
    except Exception as e:
        power = f"ERR:{e}"
    iso = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t0))
    f.write(f"{t0:.3f},{iso},{power},{temp},{sclk},{mclk}\n")
    dt = time.time() - t0
    if dt < 1.0:
        time.sleep(1.0 - dt)
f.close()
print("sampler stopped")
