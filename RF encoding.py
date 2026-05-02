import machine
import time
from machine import Timer

#pins
txser = machine.Pin(17, machine.Pin.OUT)
rxser = machine.Pin(16, machine.Pin.IN)

#backside/transcieving
class Individual:
    header = "101010101011"
    header_tuple = ["1", "0", "1", "0", "1", "0", "1", "0", "1", "0", "1", "1"]
    bit_duration = 10000 #10,000 microseconds, 10ms, 100hz
    samplerate = 800 #in hz, 1/8th of bitrate
    
    def __init__(self, footprint):
        self.tx = Transmitter(footprint)
        self.rx = Receiver(footprint)
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
        for pulse in code:
            if pulse == "1":
                txser.high()
            else:
                txser.low()
            time.sleep_us(Individual.bit_duration/2)
        txser.low()

class Receiver:
    def __init__(self, footprint):
        #id and clock
        self.footprint = footprint #identification
        self.tim = Timer(-1)
        
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
        self.decoding = True #when to stop calling decode
        
    def _callback(self, t):
        #cant allocate memory for arrays or do cpu intense in here, because it happens 800hz and GC will mess stuff up
        current_val = rxser.value()
        
        #clock recovery, reset ticks at middle of bit
        if current_val != self.prev_val:
            if self.ticks > 6:
                self.ticks = 0
                self.sampled = False
            self.prev_val = current_val
        
        self.ticks += 1
        
        #unsynced header check
        if self.ticks == 2 and not self.sampled and not self.synced:
            bit = "1" if current_val == 0 else "0"
            self.bit_buffer.append(bit)
            self.sampled = True
            
            if len(self.bit_buffer) >= 12:
                match = True
                for i in range(12):
                    if self.bit_buffer[-12 + i] != Individual.header_tuple[i]:
                        match = False
                        break
                
                if match:
                    self.synced = True
                    self.bit_buffer = []
        
        #synced data storage
        if self.ticks == 2 and not self.sampled and self.synced:
            bit = "1" if current_val == 0 else "0"
            self.bit_buffer.append(bit)
            self.sampled = True
            
        if self.ticks > 16 and self.prev_val == current_val and self.synced and len(self.bit_buffer) > 12 and not self.dataReady:
            self.dataReady = True
    
    def start(self):
        #starts listening for header(self.synced)
        self.bit_buffer = []
        self.ticks = 0
        self.synced = False
        self.tim.init(freq=Individual.samplerate, mode=Timer.PERIODIC, callback=self._callback)
        self.decoding = True
        
        while True:
            self.decode(self.bit_buffer)
            if self.decoding == False:
                break
        
    def stopclock(self):
        self.tim.deinit()
        self.decoding = False

    
    def decode(self, buffer):
        if self.dataReady:
            self.ticks = 0
            self.synced = False
            
            #convert to string and clear bit_buffer
            self.string_buffer = "".join(self.bit_buffer)
            self.bit_buffer = []
            
            if self.string_buffer[0:4] == self.footprint:
                Individual.message += chr(int(self.string_buffer[4:12], 2))
            else:
                self.synced = False
                self.bit_buffer = []
                self.ticks = 0
                self.sampled = False
                self.decoding = True
            
            self.dataReady = False

#loopback
test1 = Individual("1101")
encoded = test1.tx.encode("A")

#start listening and decoding
test1.rx.start()

#transmit
test1.tx.transmit(encoded)

#print recieved
time.sleep(1)
print(test1.message)
    

