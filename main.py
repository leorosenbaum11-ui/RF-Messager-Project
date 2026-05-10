import machine
import time
from machine import Timer

#pins
txser = machine.Pin(17, machine.Pin.OUT)
rxser = machine.Pin(16, machine.Pin.IN)
intled = machine.Pin(25, machine.Pin.OUT)

#backside/transcieving
class Individual:
    header = "101010101011"
    header_tuple = ["1", "0", "1", "0", "1", "0", "1", "0", "1", "0", "1", "1"]
    bit_duration = 10000 #10,000 microseconds, 10ms, 100hz
    samplerate = 800 #in hz, 1/8th of bitrate
    
    def __init__(self, footprint):
        self.tx = Transmitter(footprint)
        self.rx = Receiver(footprint, self)
        self.message = ""
        

class Transmitter:
    def __init__(self, footprint):
        self.footprint = footprint #identification
        
    def encode(self, char):
        #content
        charbin = f"{ord(char):08b}"
        content = "".join([self.footprint, charbin])
        
        #encoding
        manchester = "".join({"0": "01", "1": "10"}[b] for b in content)
        finaltransmit = "".join([Individual.header, manchester])
        
        return finaltransmit
    
    def transmit(self, code):
        txser.low()
        for pulse in code:
            if pulse == "1":
                txser.high()
            else:
                txser.low()
            time.sleep_us(Individual.bit_duration//2)
        txser.low()

class Receiver:
    def __init__(self, footprint, parent):
        #id and clock
        self.footprint = footprint #identification
        self.tim = Timer(-1)
        self.parent = parent
        
        #isr
        self.ticks = 0
        self.prev_val = rxser.value()
        self.bit_buffer = []
        
        #flags
        self.sampled = False #check if sampled each bit
        self.synced = False #check if locked to a transmission through header
        self.dataReady = False #check if transmission finished
        
        #decoding
        self.string_buffer = ""
        
    def _callback(self, t):
        #cant allocate memory for arrays or do cpu intense in here, because it happens 800hz and GC will mess stuff up
        current_val = rxser.value()
        
        #clock recovery, reset ticks at middle of bit
        if current_val != self.prev_val:
            if self.ticks > 6:
                #print("transition detected at tick: ", self.ticks, ", current_val at 75% of previous bit: ", current_val)
                self.ticks = 0
                self.sampled = False
            self.prev_val = current_val
        
        self.ticks += 1
        
        #unsynced header check
        if self.ticks == 2 and not self.synced or self.ticks == 6 and not self.synced:
            bit = "0" if current_val == 0 else "1"
            self.bit_buffer.append(bit)
            
            if len(self.bit_buffer) >= 12:
                match = True
                for i in range(12):
                    if self.bit_buffer[-12 + i] != Individual.header_tuple[i]:
                        match = False
                        break
                
                if match:
                    self.synced = True
                    self.bit_buffer = []
                    print("synced")
        
        #synced data storage
        if self.synced:
            if self.ticks == 2 and not self.sampled:
                bit = "1" if current_val == 0 else "0"
                self.bit_buffer.append(bit)
                self.sampled = True
            
        if self.ticks > 16 and self.prev_val == current_val and self.synced and len(self.bit_buffer) >= 12 and not self.dataReady:
            self.dataReady = True
    
    def start(self):
        #starts listening for header(self.synced)
        self.bit_buffer = []
        self.ticks = 0
        self.synced = False
        self.tim.init(freq=Individual.samplerate, mode=Timer.PERIODIC, callback=self._callback)
        self.prev_val = rxser.value()
        
    def stopclock(self):
        self.tim.deinit()
        time.sleep_ms(100)

    
    def decode(self, buffer):
        if self.dataReady:
            self.ticks = 0
            self.synced = False
            
            #convert to string and clear bit_buffer
            self.string_buffer = "".join(self.bit_buffer)
            self.bit_buffer = []
            
            if self.string_buffer[0:4] == self.footprint:
                self.parent.message += chr(int(self.string_buffer[4:12], 2))
                print("matching footprint")
            else:
                self.synced = False
                self.bit_buffer = []
                self.ticks = 0
                self.sampled = False
                print("unmatching footprint")
            
            self.dataReady = False

intled.high()

#loopback
test1 = Individual("1101")
encoded = ""

encoded += input("Add to message: ")

#start listening and decoding
test1.rx.start()


encodeds = tuple(encoded)
for char in encodeds:
    test1.tx.transmit(test1.tx.encode(char))
    time.sleep_ms(20)
    
    if test1.rx.dataReady:
        test1.rx.decode(test1.rx.bit_buffer)
        time.sleep_ms(20)
        print("recieved data: ",  test1.message)
        test1.rx.dataReady = False
        test1.rx.synced = False
        test1.rx.bit_buffer = []
        test1.rx.sampled = False

time.sleep_ms(10)
test1.rx.stopclock()

    
