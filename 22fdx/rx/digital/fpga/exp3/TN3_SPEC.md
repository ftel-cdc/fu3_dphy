# TN3 — D-PHY TX trên một board FPGA thứ hai → mạch test → RX trên board VP1902

> Đặc tả thí nghiệm cho team FPGA. Nhóm D-PHY RX viết, ngày 2026-10-19.
> Ký hiệu: ✅ đã kiểm bằng tool hoặc tài liệu (2026-10-19) · ⚠️ ước lượng hoặc giả định · 🔍 cần kiểm khi làm
>
> | Phiên bản | Ngày | Nội dung |
> |---|---|---|
> | v0.1 | 2026-10-19 | Phần 1: mục tiêu, sơ đồ, phần cứng, mạch test, bảng chân, câu hỏi. Board TX chưa chốt, vì VEK280 không dùng được (§3.2). Các mục 5–11 (design TX và RX, quy trình, tiêu chí đạt, dữ liệu gửi về, xử lý sự cố, phụ lục Tcl) sẽ viết sau, khi đã chốt board TX và mô phỏng TN2 xong |
> | v0.2 | 2026-10-26 | R-F có thêm khối chỉnh `rxactivehs` của nhóm D-PHY, giữa RX của nhóm và CSI-2 RX Subsystem (§0, §1, §2). Lý do: kết quả mô phỏng TN2b |

---

## 0. Việc cần team FPGA

1. **Chọn board TX** theo yêu cầu ở §3.2, rồi báo lại (Q1).
   - VEK280 **không** dùng được. Bank nối ra FMC của nó cố định 1.5 V, mà MIPI cần 1.2 V (§3.2).
2. **Thiết kế và làm mạch test** theo §3.3 (yêu cầu điện) và §4 (chân).
   - Phía VP1902 đã cố định (§4.1).
   - Phía TX chốt khi đã có board (§4.2).
   - Nếu board TX là một board VP1902 thứ hai cùng loại, netlist của mạch test đã có ở §4.3.
3. **Trả lời câu hỏi Q1–Q7** dưới đây.

Nhóm D-PHY sẽ build trước thiết kế FPGA cho cả hai đầu (mục 5–6), kèm script. Team FPGA cũng có thể build lại từ đặc tả.

Design R-F có thêm một khối nhỏ do nhóm D-PHY giao: `fpga/rtl/m_ftel_ppi_act_gate.sv`, 6 flip-flop với 4 lane. Khối nằm giữa RX của nhóm và CSI-2 RX Subsystem (§2):
- Ở mỗi lane, khối giữ `rxactivehs` ở mức thấp cho tới `rxsynchs`. Lý do: mô phỏng TN2b cho thấy controller CSI-2 của AMD cần hai tín hiệu này lên cùng lúc, như D-PHY của AMD.
- Mọi tín hiệu PPI khác đi thẳng, không qua khối.
- Khối chạy bằng byte clock của RX và dùng chung reset với RX.
- Nếu build lại từ đặc tả, nối khối đúng chỗ này.

| ID | Câu hỏi | Dùng cho |
|---|---|---|
| Q1 | Team có board nào đạt §3.2? Ví dụ: một board VP1902 thứ hai cùng loại, VCK190, VMK180. Nếu không phải VP1902, cho biết cách đặt VCCO 1.2 V cho bank nối ra FMC trên board đó | §3.2, §4.2 |
| Q2 | Hai board đặt ở đâu, hai connector FMC cách nhau bao xa? VP1902 nằm trong vỏ máy (user guide của board), vậy mạch test là cầu nối cứng hay dùng cáp? | §3.3 |
| Q3 | Độ dài hoặc độ trễ đường mạch từ FPGA đến connector FMC của 10 chân tín hiệu: trên VP1902 (hỏi hãng board nếu cần) và trên board TX. Hãng board có tính trễ package khi đi dây không? | bù lệch, §3.3 và §4.4 |
| Q4 | Team làm được mạch test đạt §3.3 không, và mất bao lâu? Có đo trở kháng (TDR) hoặc mô phỏng SI được không? | lịch |
| Q5 | Board TX có cần mạch test nối PRSNT_M2C_L xuống GND, hoặc có EEPROM IPMI, để bật VADJ không? | §3.3 |
| Q6 | Ai ở lab vận hành: cắm mạch test, bật/tắt nguồn, cắm lại cáp USB khi bị rớt (§3.4)? | §3.4 |
| Q7 | Có scope vi sai đủ băng thông để đo D-PHY khi cần debug không? (không bắt buộc) | debug |

---

## 1. Mục tiêu

**Câu hỏi của thí nghiệm:** RX D-PHY trên VP1902 có nhận đúng tín hiệu của một TX D-PHY thật, đi qua một đường nối thật giữa hai board, hay không?

**TX:** MIPI CSI-2 TX Subsystem của AMD, kèm D-PHY TX, phát pattern biết trước.

**RX:** chạy hai pha, cùng chân và cùng mạch test.
- **R-X (mốc):** MIPI CSI-2 RX Subsystem của AMD, có D-PHY bên trong. Lấy từ build S0 (design camera tham chiếu của board, đã cắt gọn), bỏ phần điều khiển camera.
- **R-F:** RX D-PHY của nhóm (`ftel_dphy_rx`, bản FPGA), qua khối chỉnh `rxactivehs` (§0), nối vào CSI-2 RX Subsystem không có PHY.

**Rate:** 4 lane, continuous clock.
- 800 Mb/s để bring-up;
- 1440 Mb/s là mục tiêu, bằng rate của camera IMX274;
- 1500 Mb/s là tuỳ chọn.

**Thí nghiệm chứng minh được:**
- đường nối giữa hai board (chân, mạch test, cài đặt điện áp) chạy được ở các rate trên;
- R-X nhận frame không lỗi, nên dùng được làm mốc;
- R-F cho cùng kết quả với R-X.

**Không chứng minh:**
- tương thích với camera IMX274, vì sensor có timing riêng;
- hành vi của AFE ASIC, vì bản FPGA dùng XPHY của Versal thay cho sampler;
- non-continuous clock;
- rate trên 1500 Mb/s, vì ở đó cần deskew.

Trước TN3, cấu hình IP của TX và RX đã được mô phỏng trong Vivado (TN1 và TN2). TN3 chỉ thêm phần cứng thật.

---

## 2. Sơ đồ

```
 Board TX (FPGA thứ hai)                                      Board VP1902 (RX)
 +-----------------------------------+                        +------------------------------------------+
 | nguồn pattern -> CSI-2 TX SS      |  FMC    mạch test      | FMC+ "01"                                |
 | (frame RAW10)    + D-PHY TX ======|========================|==> bank 705 -> R-X: CSI-2 RX SS + D-PHY  |
 |                  bank IO 1.2 V    |  5 cặp: CLK, D0-D3     |    1.2 V    hoặc R-F: RX nhóm -> khối    |
 |                                   |  + GND                 |             chỉnh rxactivehs -> CSI-2 RX |
 | ILA, JTAG (xsdb)                  |                        | ILA ở PPI, AXI4-Stream, LP; JTAG (xsdb)  |
 +-----------------------------------+                        +------------------------------------------+
   nguồn riêng ---------- GND chung qua mạch test (thêm dây GND riêng nếu cần, §3.3) ---------- nguồn ATX
```

Cả hai board điều khiển qua JTAG (Vivado Hardware Manager và `xsdb`), không dùng UART.

---

## 3. Phần cứng và cài đặt

### 3.1 Board RX: board VP1902

| Mục | Đặt | Nguồn |
|---|---|---|
| SW192 | **1.2 V.** SW192 chọn VCCIO 1.0 / 1.2 / 1.5 V cho bank 703–706, là các bank nối ra FMC+ "01". Mặc định 1.5 V | User guide của board ✅ |
| SW1 (boot mode) | **JTAG** | User guide của board ✅ |
| FMC+ "01" | Tháo camera, chỉ cắm mạch test | |
| Chuẩn IO trong XDC | `MIPI_DPHY` cho 10 chân ở §4.1. Không gán chân nào khác của bank 703–706 với chuẩn có điện áp khác 1.2 V | User guide của board: đổi VCCIO thì phải đổi IOSTANDARD theo ✅ |

JTAG là một cổng USB-C ở mặt trước (user guide của board) ✅. Lưu ý vận hành ở §3.4.

### 3.2 Board TX

**Yêu cầu:**

| # | Yêu cầu | Lý do |
|---|---|---|
| T1 | FPGA của AMD có D-PHY TX trong IO: XPIO của Versal, hoặc HP IO của UltraScale+. Vivado 2025.2 cho dùng MIPI CSI-2 TX Subsystem 4 lane, 1500 Mb/s trên part đó 🔍 | TX dùng IP của AMD (§1) |
| T2 | Connector FMC hoặc FMC+ có ít nhất 5 cặp vi sai nằm chung một bank IO | Cần 1 clock lane + 4 data lane. Luật đặt chân của IP do Vivado kiểm (DRC lúc place) 🔍 |
| T3 | VCCO của bank đó đặt được 1.2 V, và trên board không có thiết bị nào khác cần bank đó chạy ở điện áp khác | Chuẩn `MIPI_DPHY` cần VCCO 1.2 V: theo device data của Vivado 2025.2, VCCO_IN = VCCO_OUT = 1.200 ✅ |
| T4 | Nạp và debug được qua JTAG (Hardware Manager, ILA, `xsdb`) | Điều khiển không cần UART |
| T5 | Đặt được đủ gần VP1902 để đường nối đạt §3.3 (thời gian bay ≤ 2 ns) | D-PHY |

**Các board đã xét:**

| Board | Kết luận | Bằng chứng |
|---|---|---|
| VEK280 | **Không dùng được.** Cả 72 chân LA và CLK của FMCP1 đều nằm ở bank 705 (36 chân) và 706 (36 chân) ✅. Hai bank này nối vào VADJ_FMC, cố định 1.5 V | AMD UG1612 rev 1.1, mục "LPD MIO[23]: VADJ_FMC Power Rail": *"VADJ_FMC and VADJ_FMC_BUS for the VEK280 is fixed to 1.5V at boot"* và *"Banks 705 and 706 are tied to VADJ_FMC"*. README trong board file VEK280 của Vivado cũng ghi theo schematic thì bank 705/706 chạy 1.5 V, trong khi MIPI cần 1.2 V. Bảng bank lấy từ probe `tn3_pins` |
| Board VP1902 thứ hai cùng loại | **Đạt T2, T3.** Trên FMC+ "01", 5 cặp chân camera nằm chung bank 705 ✅ (§4.1), và SW192 đặt được 1.2 V ✅. Mạch test nối thẳng các chân cùng tên (§4.3) | Netlist và user guide của board |
| VCK190, VMK180 | **Có thể.** Theo nguồn ngoài AMD, system controller đặt được VADJ_FMC 1.2 V, dựa trên EEPROM của card FMC hoặc ghi I2C thẳng vào regulator 🔍. Team kiểm user guide của board rồi chọn chân | Một bài viết ngoài AMD; team kiểm lại theo user guide của AMD cho VCK190 và VMK180 🔍 |

Board khác cũng dùng được nếu đạt T1–T5.

### 3.3 Mạch test

**Nối những gì:**
- Chỉ nối 10 chân tín hiệu (5 cặp: CLK, D0, D1, D2, D3) và GND.
- Mọi chân khác để hở ở **cả hai đầu**, nhất là các chân nguồn và quản lý: VADJ, 3P3V, 3P3VAUX, 12P0V, VIO_B_M2C, PG_C2M, PG_M2C, PRSNT_M2C_L, SCL/SDA, GA0/GA1 và JTAG của FMC.
  - Hai board đều cấp điện ra các chân này. Nối chéo là chập nguồn của hai board.
  - Ví dụ trên VP1902: các chân VADJ của FMC+ "01" (E39, F40, G39, H40) nối vào net `VADJ_FMC1_1.5V` qua R235, R236, R237 và R239. Chân 3P3V nối vào `VCC_3.3V`, chân 12P0V nối vào `VCC_12V` (netlist của board) ✅.
- Phía VP1902 chỉ dùng hàng C, G và H của connector (§4.1). Các hàng này có trong cả đầu cắm LPC, nên team được chọn đầu cắm mezzanine loại LPC, HPC hay HSPC.

**Yêu cầu điện:**

| # | Yêu cầu | Giá trị | Nguồn |
|---|---|---|---|
| E1 | Trở kháng vi sai | 100 Ω ±10 % | UG863; D-PHY v1.1 lấy 100 Ω vi sai, 50 Ω mỗi dây và 25 Ω common mode làm mức tham chiếu |
| E2 | Ghép cặp lỏng | Stripline. Khoảng cách trong cặp bằng 2.5 lần bề rộng dây; tới cặp MIPI khác 5 lần; tới dây khác 6 lần | UG863. D-PHY khuyên ghép lỏng, vì cùng đôi dây còn chạy LP đơn cực |
| E3 | Mặt phẳng tham chiếu | GND liền bên dưới mọi dây, kể cả qua connector và via. Có dây hoặc vùng GND xen giữa các cặp. Đặt via GND cạnh via tín hiệu ⚠️ | D-PHY: mặt tham chiếu sát mọi dây, liền mạch qua connector, xen GND giữa các cặp. Via GND là cách làm thường dùng, không phải yêu cầu của D-PHY |
| E4 | Ghép DC | Không tụ nối tiếp, không điện trở nối tiếp, không điện trở termination trên mạch test. RX dùng termination 100 Ω trong chip (`DIFF_TERM_ADV TERM_100` trong XDC của design camera tham chiếu) ✅ | UG863: khi RX là FPGA AMD thì dùng termination trong chip. Ở chế độ LP, đường dây phải là trở kháng cao, ghép DC |
| E5 | Không stub | Không test point, không nhánh rẽ trên 10 dây tín hiệu | |
| E6 | Thời gian bay | ≤ 2 ns cho cả đường nối giữa hai chip: đường mạch trên hai board, cộng mạch test và cáp. Trên PCB thông thường, con số này ứng với khoảng 25–30 cm | D-PHY |
| E7 | Lệch P/N trong một cặp | ±2 ps, **tính cả trễ package** | UG863 |
| E8 | Lệch clock–data và data–data | ≤ 0.075 UI, **tính cả trễ package**. Mục tiêu tốt hơn: riêng phần đường nối (không tính package) lệch < UI/50 | UG863 (0.075 UI); D-PHY (UI/50) |
| E9 | Insertion loss | Nằm trong template của D-PHY | UG863 |
| E10 | Điện trở nối tiếp của mỗi dây | < 5 Ω, tính cả điện trở tiếp xúc của connector | D-PHY |
| E11 | GND giữa hai board | Điện trở đường GND < 0.2 Ω. Lệch GND DC < 50 mV khi đang chạy | D-PHY |

**Ngân sách lệch theo rate.** Thiết kế theo 1500 Mb/s.

| Rate (Mb/s) | UI (ps) | 0.075 UI (ps): bắt buộc, tính cả package | UI/50 (ps): mục tiêu cho đường nối |
|---|---|---|---|
| 800 | 1250.0 | 93.8 | 25.0 |
| 1440 | 694.4 | 52.1 | 13.9 |
| 1500 | 666.7 | 50.0 | 13.3 |

Quy đổi ⚠️: với stripline FR-4 (εr ≈ 4), 1 mm ≈ 6.7 ps. Như vậy ±2 ps ≈ ±0.3 mm, 13.3 ps ≈ 2 mm và 50 ps ≈ 7.5 mm.

**Bù lệch.**
- Trễ tổng của một lane = package TX + đường mạch trên board TX + mạch test + đường mạch trên VP1902 + package VP1902.
- Đã biết: trễ package của VP1902 (§4.4), và trễ package của board TX khi đã chọn chân (lấy bằng probe tương tự).
- Chưa biết: trễ đường mạch trên hai board (Q3).
- Mạch test chỉnh độ dài từng dây sao cho trễ tổng của các lane bằng nhau, trong giới hạn E7 và E8.
- Riêng package VP1902 đã cần bù: so với clock, D1 sớm 38.9 ps và D0 trễ 12.7 ps (§4.4).

**Cách làm mạch test** (team chọn, cách nào cũng phải đạt E1–E11):

| Cách | Ưu | Nhược |
|---|---|---|
| (a) Một cầu nối cứng, cắm cùng lúc vào hai connector | Ít điểm gián đoạn, đường ngắn | Hai connector phải cùng độ cao và đúng khoảng cách; khó làm nếu VP1902 vẫn nằm trong vỏ máy |
| (b) Hai card mezzanine nhỏ nối bằng cáp đồng trục hoặc twinax đã khớp trễ | Đặt hai board linh hoạt | Mỗi đầu cáp thêm một chỗ gián đoạn trở kháng (D-PHY lưu ý về connector). Bộ cáp phải khớp trễ theo E7–E8 |
| (c) Flex | Gọn | Phải đạt E1–E3 trên vật liệu flex |

**Equalization.** Nếu đường nối dài hoặc tổn hao lớn, RX có thể cần bật equalization. UG863 bảo quyết định việc này theo D-PHY và theo khuyến nghị SI của AMD. Nhóm D-PHY sẽ quyết khi có số liệu kênh (Q2, Q3) 🔍.

**GND giữa hai board.** Để đạt E11:
- nối mọi chân GND trên cả hai connector;
- nếu đo thấy lệch GND quá 50 mV, thêm một dây GND tiết diện lớn nối thẳng hai board;
- cắm hai bộ nguồn chung một ổ điện ⚠️.

### 3.4 Quy tắc vận hành

1. **Kiểm VCCO trước khi nối.**
   - Trên VP1902: SW192 = 1.2 V.
   - Trên board TX: bank TX = 1.2 V, đo bằng đồng hồ hoặc đọc lại qua system controller.

   Chỉ cắm mạch test khi cả hai đều đúng. Nếu một đầu còn ở 1.5 V thì mức LP cao lên khoảng 1.5 V. Mức này vượt mức tối đa 1.3 V mà D-PHY cho phép ở ngõ ra LP, và cao hơn VCCO của bank bên kia.
2. **Chỉ cắm hoặc rút mạch test khi cả hai board đã tắt.**
3. **Hai bộ nguồn cắm chung một ổ điện.** Nối GND giữa hai board trước khi bật.
4. **Thứ tự bật:**
   1. bật VP1902 (RX), rồi bật board TX;
   2. nạp RX trước, nạp TX sau;
   3. TX chỉ bắt đầu phát sau khi RX đã nạp xong.

   **Thứ tự tắt:**
   1. dừng TX (giữ ở reset);
   2. tắt board TX;
   3. tắt VP1902.

   Lý do: không để board đang chạy đẩy mức 1.2 V vào chân của board đang tắt, vì dòng sẽ chạy ngược qua diode bảo vệ vào nguồn của board đó.
5. **USB của VP1902 hay rớt.**
   - Theo log của máy station ngày 15–17/10, cổng USB JTAG và UART của VP1902 đã rớt khỏi máy ở các lần bật nguồn, nạp và tắt-bật nguồn.
   - Sau mỗi lần rớt, phải cắm lại cáp thì máy mới nhận lại.
   - Vì vậy, mỗi lần bật/tắt nguồn hoặc nạp cần có người ở lab. Trên máy station, theo dõi bằng `dmesg -wT`.

---

## 4. Bảng chân

### 4.1 Phía RX: board VP1902, FMC+ "01", bank 705 (cố định)

| Lane | Net trên board | Chân FMC P / N | Ball P / N | Site (chân P) | Nibble |
|---|---|---|---|---|---|
| CLK | `F_FMC1_CLK0_M2C_P/N` | H4 / H5 | CV60 / CV59 | `IO_L9P_GC_XCC_N3P0_M1P126_705` | 3 |
| D0 | `F_FMC1_LA10_P/N` | C14 / C15 | CY61 / DA61 | `IO_L1P_N0P2_M1P110_705` | 0 |
| D1 | `F_FMC1_CLK1_M2C_P/N` | G2 / G3 | CT61 / CU61 | `IO_L6P_GC_XCC_N2P0_M1P120_705` | 2 |
| D2 | `F_FMC1_LA08_P/N` | G12 / G13 | DC60 / DC59 | `IO_L5P_N1P4_M1P118_705` | 1 |
| D3 | `F_FMC1_LA06_P/N` | C10 / C11 | DA60 / DA59 | `IO_L2P_N0P4_M1P112_705` | 0 |

Nguồn ✅:
- net, chân FMC và ball lấy từ netlist của board;
- XDC của design camera tham chiếu gán đúng các ball này;
- site và nibble lấy từ device data của Vivado (probe `tn3_pins`).

Mỗi net chỉ nối một chân connector với một ball FPGA, không có linh kiện nào trên đường (netlist) ✅.

Đây là chân của module camera. Vì vậy R-X và R-F dùng đúng các chân mà camera sẽ dùng.

### 4.2 Phía TX: luật chọn chân

- 5 cặp nằm chung một bank IO có VCCO 1.2 V (T2, T3).
- Giữ đúng thứ tự lane: CLK → CLK, D0 → D0, …, D3 → D3.
- **Không đảo P/N.** Ở chế độ LP, D-PHY dùng từng dây riêng, ví dụ LP-01 khác LP-10. Đảo P/N sẽ làm sai trạng thái LP.
- Luật đặt chân của D-PHY TX do Vivado kiểm khi place. Team chạy thử I/O planning trên board TX trước khi chốt mạch test 🔍.
- Bảng chân TX sẽ chốt khi đã có board TX (Q1).

### 4.3 Trường hợp board TX là một board VP1902 thứ hai cùng loại

TX dùng đúng 5 cặp cùng tên trên FMC+ "01" của board TX: cùng bank 705, cùng ball như §4.1. Mạch test nối thẳng:

| Lane | Board TX: chân FMC+ "01" (P / N) | → | Board RX: chân FMC+ "01" (P / N) |
|---|---|---|---|
| CLK | H4 / H5 | → | H4 / H5 |
| D0 | C14 / C15 | → | C14 / C15 |
| D1 | G2 / G3 | → | G2 / G3 |
| D2 | G12 / G13 | → | G12 / G13 |
| D3 | C10 / C11 | → | C10 / C11 |
| GND | mọi chân GND | → | mọi chân GND |

Mọi chân khác để hở (§3.3).

Lưu ý:
- Theo tên chuẩn FMC, CLK0_M2C và CLK1_M2C là chiều mezzanine → carrier. Trên VP1902, chúng chỉ là chân IO thường của FPGA (netlist: nối thẳng vào ball), nên dùng để phát được ✅.
- Hai board giống hệt nhau, nên lệch của package và của đường mạch trên board **cộng đôi**, không triệt tiêu nhau (§4.4).

### 4.4 Trễ package phía VP1902

Số liệu lấy từ device data của Vivado 2025.2, probe `tn3_pins`, cho 10 chân ở §4.1. Đơn vị ps; mỗi ô P/N là khoảng min–max.

| Lane | P | N | Trung bình cặp | N − P | Lane − CLK |
|---|---|---|---|---|---|
| CLK | 173.1–174.9 | 176.3–178.1 | 175.6 | +3.2 | 0 |
| D0 | 189.6–191.5 | 185.1–186.9 | 188.3 | −4.6 | +12.7 |
| D1 | 138.6–139.9 | 133.5–134.8 | 136.7 | −5.1 | −38.9 |
| D2 | 175.2–176.9 | 180.5–182.4 | 178.7 | +5.4 | +3.1 |
| D3 | 182.7–184.5 | 188.4–190.3 | 186.5 | +5.7 | +10.9 |

**Đọc bảng:**
- Chỉ riêng package VP1902 đã làm D1 đến sớm hơn clock 38.9 ps. Ở 1500 Mb/s, giới hạn E8 là 50 ps.
- Mọi cặp đều lệch P/N 3–6 ps ngay trong package, tức là đã vượt ±2 ps của E7 nếu không bù.
- Trường hợp §4.3 (hai VP1902), các số trên nhân đôi:
  - lệch so với clock: D1 −77.8 ps, D0 +25.3 ps, D3 +21.7 ps, D2 +6.3 ps;
  - N − P: từ −10.2 đến +11.4 ps.

  Mạch test phải bù các lệch này. Ví dụ, dây D1 phải dài hơn dây CLK khoảng 78 ps, tức khoảng 12 mm trên FR-4 ⚠️. Ngoài ra còn phải cộng phần lệch của đường mạch trên board (Q3).
- Nếu hãng board đã tính trễ package khi đi dây, phần bù trên mạch test giảm tương ứng (Q3).

Về đơn vị: device data lưu `MIN_DELAY`/`MAX_DELAY` theo fs. Lệnh `write_csv` của Vivado in đúng các số đó theo ps, ở cột "Min/Max Trace Delay (ps)" ✅.

---

## Nguồn

- MIPI Alliance, *Specification for D-PHY*, v1.1.
- AMD UG863, *Versal Adaptive SoC PCB Design User Guide*, rev 1.12 (2026-06-16), mục "MIPI D-PHY": <https://docs.amd.com/r/en-US/ug863-versal-pcb-design/MIPI-D-PHY>.
- AMD UG1612, *VEK280 Evaluation Board User Guide*, rev 1.1 (2024-01-31), mục "LPD MIO[23]: VADJ_FMC Power Rail": <https://docs.amd.com/r/en-US/ug1612-vek280-eval-bd/LPD-MIO-23-VADJ_FMC-Power-Rail>.
- Board file VEK280 1.2 trong Vivado 2025.2: `/opt/xilinx/2025.2/data/xhub/boards/XilinxBoardStore/boards/Xilinx/vek280/production/1.2/` (`README.md`, `part0_pins.xml`).
- User guide và netlist của board VP1902, XDC của design camera tham chiếu: tài liệu của hãng board, giữ nội bộ.
- Probe `fpga/probe/tn3_pins.tcl`, chạy bằng `fpga/probe/run_probe.sh tn3_pins` (khoảng 30 giây, 3 GB RAM). Kết quả ở `fpga/work/tn3_pins/probe.txt`.
