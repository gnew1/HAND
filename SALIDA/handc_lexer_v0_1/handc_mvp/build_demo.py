import os, subprocess, sys, json, pathlib
base = pathlib.Path(__file__).resolve().parent
handc = base / "handc.py"
examples = base / "examples"
dist = base / "dist_demo"
for name in ["hello.hand","input_positive.hand","loop.hand","function_sum.hand","sql_table.hand"]:
    inp = examples / name
    outp = dist / name.replace(".hand","")
    outp.mkdir(parents=True, exist_ok=True)
    subprocess.check_call([sys.executable, str(handc), str(inp), "--target", "python", "--out", str(outp), "--emit-ir", str(outp/"program.ir.json")])
print("done")
