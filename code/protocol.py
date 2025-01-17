import platform
import struct
from pymodbus.client import ModbusSerialClient as ModbusClient
from pymodbus.client import ModbusTcpClient

class Binary():
    """
    Binary Class
    """
    def decimal_to_binary(self, decimal_num):
        """
        This function converts base 10 to base 2
        """
        binary_num = ""
        while decimal_num > 0:
            binary_num = str(decimal_num % 2) + binary_num
            decimal_num = decimal_num // 2
        # Fill to 16 digits with 0
        if len(binary_num) < 16:
            binary_num = "0"*(16-len(binary_num)) + binary_num
        return binary_num
        
    def binary_to_decimal(self, binary_num):
        """
        This function converts base 2 to base 10
        """
        decimal_num = 0
        for i in range(len(binary_num)):
            decimal_num += int(binary_num[i]) * (2 ** (len(binary_num)-i-1))
        return decimal_num
    
    def binary_crop(self, digit, binary_num):
        """
        This function crops the last n digits of the binary number
        """
        return binary_num[len(binary_num)-digit:]

    def binary_twos_complement(self, number):
        """
        This functions converts the (negative) number to its 16-bit two's complement representation
        """
        if number < 0:
            number = (1 << 16) + number  # Adding 2^16 to the negative number
        return number
    
    def binary_reverse_twos_complement(self, number):
        """
        This functions converts the 16-bit two's complement number back to its original signed representation 
        """
        if number & (1 << 15):  # Check if the most significant bit is 1
            number = number - (1 << 16)  # Subtract 2^16 from the number
        return number

class Protocol_Y(Binary):
    """
    Protocol Y Class
    """
    def __init__(self):
        self.os = platform.platform()[0].upper()
        if self.os == 'M': #Mac
            self.port = "/dev/cu.usbmodem14103"
        elif self.os == 'W': #Windows        
            self.port = "COM16"

        self.usb_connect = False
        self.usb_connect_before = False

        self.slave_address = 0x15
        self.register = []
        
        self.routine_normal = True

        self.laser_on = "0"
        self.gripper_power = "0"
        self.gripper_pick = "0"
        self.gripper_place = "0"
        self.y_axis_moving_status_before = "Idle"
        self.y_axis_moving_status = "Idle"
        self.y_axis_actual_pos = 0.0
        self.y_axis_actual_spd = 0.0
        self.y_axis_actual_acc = 0.0
        self.x_axis_moving_status_before = "Idle"
        self.x_axis_moving_status = "Idle"

        self.goal_point_x_register = 0

        self.client = ModbusClient(method="rtu", port=self.port, stopbits=1, bytesize=8, parity="E", baudrate=19200)
        print('y-Axis Connection Status :', self.client.connect())

        self.write_heartbeat() # Write heartbeat as "Hi"
        
    def heartbeat(self):
        if self.read_hearbeat() == 22881: # Read heartbeat as "Ya"
            self.write_heartbeat() # Write heartbeat as "Hi"
            return True
        else:
            return False

    def routine(self):
        try:
            self.register = self.client.read_holding_registers(address=0x00, count=0x46, slave=self.slave_address).registers
            self.read_end_effector_status()
            self.read_y_axis_moving_status()
            self.read_x_axis_moving_status()
            self.read_y_axis_actual_motion()
            print("Laser:", self.laser_on)
            print("Gripper:", self.gripper_power, "\tPick:", self.gripper_pick, "\tPlace:", self.gripper_place)
            print("Pos:", self.y_axis_actual_pos, "\tSpd:", self.y_axis_actual_spd, "\tAcc:", self.y_axis_actual_acc)
            print("Y-Axis Moving:", self.y_axis_moving_status)
            print("X-Axis Moving:", self.x_axis_moving_status)
            self.routine_normal = True
        except Exception as e:
            print("Routine Error", e)
            self.routine_normal = False

    def read_hearbeat(self):
        try:
            hearbeat_value = self.client.read_holding_registers(address=0x00, count=1, slave=self.slave_address).registers
        except Exception as e:
            print("Heartbeat Error", e)
            return "Error"
        return hearbeat_value[0]
    
    def write_heartbeat(self):
        try:
            self.client.write_register(address=0x00, value=18537, slave=self.slave_address)
            self.usb_connect = True
        except:
            self.usb_connect = False

    def write_base_system_status(self, command):
        if command == "Set Pick Tray":
            self.base_system_status_register = 0b00001
        elif command == "Set Place Tray":
            self.base_system_status_register = 0b00010
        elif command == "Home":
            self.base_system_status_register = 0b00100
        elif command == "Run Tray Mode":
            self.base_system_status_register = 0b01000
        elif command == "Run Point Mode":
            self.base_system_status_register = 0b10000
        self.client.write_register(address=0x01, value=self.base_system_status_register, slave=self.slave_address)
        print("Write Base System Status to Client")

    def read_end_effector_status(self):
        end_effector_status_binary = self.binary_crop(4, self.decimal_to_binary(self.register[0x02]))[::-1]
        self.laser_on      = end_effector_status_binary[0]
        self.gripper_power = end_effector_status_binary[1]
        self.gripper_pick  = end_effector_status_binary[2]
        self.gripper_place = end_effector_status_binary[3]

    def write_end_effector_status(self, command):
        if command == "Laser On":
            self.end_effector_status_register = 0b0001
        elif command == "Laser Off":
            self.end_effector_status_register = 0b0000
        elif command == "Gripper Power On":
            self.end_effector_status_register = 0b0010
        elif command == "Gripper Power Off":
            self.end_effector_status_register = 0b0000
        elif command == "Gripper Pick":
            self.end_effector_status_register = 0b0110
        elif command == "Gripper Place":
            self.end_effector_status_register = 0b1010
        self.client.write_register(address=0x02, value=self.end_effector_status_register, slave=self.slave_address)

    def read_y_axis_moving_status(self):
        self.y_axis_moving_status_before = self.y_axis_moving_status
        y_axis_moving_status_binary = self.binary_crop(6, self.decimal_to_binary(self.register[0x10]))[::-1]
        if y_axis_moving_status_binary[0] == "1":
            self.y_axis_moving_status = "Jog Pick"
        elif y_axis_moving_status_binary[1] == "1":
            self.y_axis_moving_status = "Jog Place"
        elif y_axis_moving_status_binary[2] == "1":
            self.y_axis_moving_status = "Home"
        elif y_axis_moving_status_binary[3] == "1":
            self.y_axis_moving_status = "Go Pick"
        elif y_axis_moving_status_binary[4] == "1":
            self.y_axis_moving_status = "Go Place"
        elif y_axis_moving_status_binary[5] == "1":
            self.y_axis_moving_status = "Go Point"
        else:
            self.y_axis_moving_status = "Idle"

    def read_y_axis_actual_motion(self):
        self.y_axis_actual_pos = self.binary_reverse_twos_complement(self.register[0x11]) / 10
        self.y_axis_actual_spd = self.register[0x12] / 10
        self.y_axis_actual_acc = self.register[0x13] / 10

    def read_pick_tray_position(self):
        # Origin x
        self.pick_tray_origin_x = self.binary_reverse_twos_complement(self.register[0x20]) / 10
        # Origin y
        self.pick_tray_origin_y = self.binary_reverse_twos_complement(self.register[0x21]) / 10
        # Orientation
        self.pick_tray_orientation = self.register[0x22] / 100

    def read_place_tray_position(self):
        # Origin x
        self.place_tray_origin_x = self.binary_reverse_twos_complement(self.register[0x23]) / 10
        # Origin y
        self.place_tray_origin_y = self.binary_reverse_twos_complement(self.register[0x24]) / 10
        # Orientation
        self.place_tray_orientation = self.register[0x25] / 100

    def write_goal_point(self, x, y):
        self.goal_point_x_register = self.binary_twos_complement(int(x*10))
        self.goal_point_y_register = self.binary_twos_complement(int(y*10))
        self.client.write_register(address=0x30, value=self.goal_point_x_register, slave=self.slave_address)
        self.client.write_register(address=0x31, value=self.goal_point_y_register, slave=self.slave_address)

    def read_x_axis_moving_status(self):
        self.x_axis_moving_status_before = self.x_axis_moving_status
        x_axis_moving_status_binary = self.binary_crop(4, self.decimal_to_binary(self.register[0x40]))[::-1]
        if x_axis_moving_status_binary[0] == "1":
            self.x_axis_moving_status = "Home"
        elif x_axis_moving_status_binary[1] == "1":
            self.x_axis_moving_status = "Run"
        elif x_axis_moving_status_binary[2] == "1":
            self.x_axis_moving_status = "Jog Left"
        elif x_axis_moving_status_binary[3] == "1":
            self.x_axis_moving_status = "Jog Right"
        else:
            self.x_axis_moving_status = "Idle"

    def write_x_axis_moving_status(self, command):
        if command == "Home":
            self.x_axis_moving_status_register = 0b01
        elif command == "Run":
            self.x_axis_moving_status_register = 0b10
        elif command == "Idle":
            self.x_axis_moving_status_register = 0b00
        if self.usb_connect:
            self.client.write_register(address=0x40, value=self.x_axis_moving_status_register, slave=self.slave_address)

    def read_x_axis_target_motion(self):
        self.x_axis_target_pos = self.binary_reverse_twos_complement(self.register[0x41]) / 10
        self.x_axis_target_spd = self.register[0x42] / 10
        self.x_axis_target_acc_time = self.register[0x43]

    def write_x_axis_actual_motion(self, pos, spd):
        self.x_axis_actual_pos_register = self.binary_twos_complement(int(pos * 10))
        self.x_axis_actual_spd_register = int(spd * 10)
        if self.usb_connect:
            self.client.write_register(address=0x44, value=self.x_axis_actual_pos_register, slave=self.slave_address)
            self.client.write_register(address=0x45, value=self.x_axis_actual_spd_register, slave=self.slave_address)


class Protocol_X(Binary):
    """
    Protocol X Class
    """
    def __init__(self):
        self.host = "192.168.3.250"

        self.register = [0,0,0,0,0,0] # Temporary (should be [])

        self.x_axis_moving_status_before = "Idle"
        self.x_axis_moving_status = "Idle"

        self.x_axis_actual_pos = 0.0
        self.x_axis_actual_spd = 0.0
        self.x_axis_actual_acc = 0.0

        self.client= ModbusTcpClient(self.host)

        self.connection = self.client.connect()
        print('x-Axis Connection Status :', self.connection)

        if self.connection:
            self.write_x_axis_moving_status("Home")

    def read_holding_registers(self):
        self.register = self.client.read_holding_registers(address=0x00, count=5).registers

    def write_x_axis_moving_status(self, command):
        if command == "Idle":
            self.x_axis_moving_status_register = 0b0000
        elif command == "Home":
            self.x_axis_moving_status_register = 0b0001
        elif command == "Run":
            self.x_axis_moving_status_register = 0b0010
        elif command == "Jog Left":
            self.x_axis_moving_status_register = 0b0100
        elif command == "Jog Right":
            self.x_axis_moving_status_register = 0b1000
        self.client.write_register(address=0x00, value=self.x_axis_moving_status_register)

    def read_x_axis_moving_status(self):
        self.x_axis_moving_status_before = self.x_axis_moving_status
        x_axis_moving_status_binary = self.binary_crop(4, self.decimal_to_binary(self.register[0x00]))[::-1]
        if x_axis_moving_status_binary[0] == "1":
            self.x_axis_moving_status = "Home"
        elif x_axis_moving_status_binary[1] == "1":
            self.x_axis_moving_status = "Run"
        elif x_axis_moving_status_binary[2] == "1":
            self.x_axis_moving_status = "Jog Left"
        elif x_axis_moving_status_binary[3] == "1":
            self.x_axis_moving_status = "Jog Right"
        else:
            self.x_axis_moving_status = "Idle"

    def read_x_axis_actual_motion(self):
        actual_pos_struct = struct.pack("HH", self.register[0x01], self.register[0x02])
        self.x_axis_actual_pos = int((struct.unpack("i", actual_pos_struct)[0]) / 1000) / 10.0 # mm
        actual_spd_struct = struct.pack("HH", self.register[0x03], self.register[0x04])
        self.x_axis_actual_spd = int((struct.unpack("I", actual_spd_struct)[0]) / 1000) / 10.0 # mm/s

    def write_x_axis_target_motion(self, pos, spd, acc_time):
        # Limit position range between -140 to 140 mm 
        if pos < -140:
            pos = -140
        elif pos > 140:
            pos = 140
        target_pos_struct   = struct.pack("i", int(pos*10000))
        target_pos_register = struct.unpack("HH", target_pos_struct)
        spd = min(spd, 300) # Limit maximum speed to 300 mm/s
        target_spd_struct   = struct.pack("I", int(spd*60*100))
        target_spd_register = struct.unpack("HH", target_spd_struct)
        target_acc_time_register = acc_time
        self.client.write_registers(address=0x05, values=[target_pos_register[0], target_pos_register[1], target_spd_register[0], target_spd_register[1], target_acc_time_register])