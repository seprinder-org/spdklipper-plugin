import asyncio
import os
import sys
import traceback
from io import BytesIO

sys.path.append(os.getcwd())

log_file = "./mock/test_klipper_output.txt"

def log(msg):
    with open(log_file, "a") as f:
        f.write(msg + "\n")
    print(msg)

async def test_mock_klipper():
    log("Initializing Mock Klipper Printer...")
    try:
        from src.printer.klipper import KlipperPrinter
        printer = KlipperPrinter("http://localhost:7125", mock=True)
        
        log("--- Testing getInfoMachine ---")
        info = await printer.getInfoMachine()
        log(f"Info Machine: {info}")

        log("--- Testing getTemperature ---")
        temp = await printer.getTemperature()
        log(f"Temperature: {temp}")
        
        log("--- Testing runHome ---")
        home = await printer.runHome()
        log(f"Home Result: {home}")

        log("--- Testing getPrintStat ---")
        stat = await printer.getPrintStat()
        log(f"Print Stat: {stat}")

        log("--- Testing isReadyState ---")
        is_ready = await printer.isReadyState()
        log(f"Is Ready: {is_ready}")
        
        log("--- Testing uploadFile ---")
        dummy_file = BytesIO(b"G1 X10 Y10")
        uploaded = await printer.uploadFile("test.gcode", dummy_file)
        log(f"Uploaded (Path): {uploaded}")

        log("--- Testing printModel ---")
        started = await printer.printModel("test.gcode")
        log(f"Start Job Result: {started}")

        log("--- Testing runPause ---")
        paused = await printer.runPause()
        log(f"Pause Result: {paused}")

        log("--- Testing runResume ---")
        resumed = await printer.runResume()
        log(f"Resume Result: {resumed}")

        log("--- Testing runCancel ---")
        cancelled = await printer.runCancel()
        log(f"Cancel Result: {cancelled}")

        log("--- Testing removeFile ---")
        removed = await printer.removeFile("test.gcode")
        log(f"Remove Result: {removed}")

        log("--- Testing captureImage ---")
        img_path = "mock_capture_klipper.jpg"
        captured = await printer.captureImage("http://camera/stream", img_path)
        log(f"Capture Result: {captured}")
        if captured and os.path.exists(img_path):
            log(f"Image saved at {img_path}")
            os.remove(img_path)

        log("--- Testing runRestart ---")
        restarted = await printer.runRestart()
        log(f"Restart Result: {restarted}")

        log("--- Testing runScript ---")
        script_res = await printer.runScript("G28 X0")
        log(f"Script Result: {script_res}")

        log("--- Testing doJob (Base) ---")
        # In mock mode, isReadyState returns True if state is 'complete' or 'standby'
        # With the current mock getPrintStat, state is 'complete', so this should finish.
        job_result = await printer.doJob("test.gcode")
        log(f"doJob Result: {job_result}")

    except Exception as e:
        log(f"Error: {e}")
        log(traceback.format_exc())

if __name__ == "__main__":
    if not os.path.exists("./mock"):
        os.makedirs("./mock")
    with open(log_file, "w") as f:
        f.write("Start Mock Klipper Test\n")
    asyncio.run(test_mock_klipper())
