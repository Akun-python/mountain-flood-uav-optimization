import sys
sys.path.insert(0, '求解代码与结果/实验'); sys.path.insert(0, '求解代码与结果/代码')
from p2_solve import Flight
import inspect
print(inspect.signature(Flight.delivery_times))
print(inspect.getsource(Flight.delivery_times)[:600])
