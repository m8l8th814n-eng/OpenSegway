"""Ghidra script that finds UART baud rates and USART register references."""

from ghidra.program.model.scalar import Scalar

BAUDS = [
    1200,
    2400,
    4800,
    9600,
    19200,
    38400,
    57600,
    115200,
    230400,
    250000,
    460800,
    921600,
]


USART_BASES = {
    0x40013800: "USART1",
    0x40004400: "USART2",
    0x40004800: "USART3",
    0x40004C00: "USART4",
    0x40005000: "USART5",
    0x40008000: "LPUART1",
    0x40011000: "USART1(G0-alt)",
}
REG_NAMES = {
    0x00: "CR1",
    0x04: "CR2",
    0x08: "CR3",
    0x0C: "BRR",
    0x10: "GTPR",
    0x1C: "RDR",
    0x20: "TDR",
}

listing = currentProgram.getListing()
fm = currentProgram.getFunctionManager()

hits_baud = []
hits_reg = []

for ins in listing.getInstructions(True):
    for i in range(ins.getNumOperands()):
        for op in ins.getOpObjects(i):
            if isinstance(op, Scalar):
                v = op.getValue()
                if v in BAUDS:
                    hits_baud.append((ins.getAddress(), v, str(ins)))

                if 0x40000000 <= v <= 0x4002FFFF:
                    for b, nm in USART_BASES.items():
                        off = v - b
                        if 0 <= off <= 0x2C:
                            reg = REG_NAMES.get(off, "off+%02X" % off)
                            hits_reg.append(
                                (ins.getAddress(), "%s.%s" % (nm, reg), str(ins))
                            )
                            break
            else:

                try:
                    av = op.getAddress().getOffset()
                except Exception:
                    continue
                for b, nm in USART_BASES.items():
                    off = av - b
                    if 0 <= off <= 0x2C:
                        reg = REG_NAMES.get(off, "off+%02X" % off)
                        hits_reg.append(
                            (ins.getAddress(), "%s.%s" % (nm, reg), str(ins))
                        )
                        break


def fname(addr):
    f = fm.getFunctionContaining(addr)
    return str(f.getName()) if f else "-"


print("\n================ BAUD CONSTANTS (operand = baud) ================")
for addr, v, txt in hits_baud:
    print("%s  baud=%-7d in %-28s  %s" % (addr, v, fname(addr), txt))

print("\n================ USART REGISTER REFERENCES ================")
for addr, reg, txt in hits_reg:
    print("%s  %-18s in %-28s  %s" % (addr, reg, fname(addr), txt))

print(
    "\nSUMMARY: %d baud occurrences, %d register references"
    % (len(hits_baud), len(hits_reg))
)
