# TN2b: frame RAW10 qua CSI-2 TX Subsystem của AMD vào hai đường nhận CSI-2, mô phỏng XSIM

Thí nghiệm TN2b của [`../PLAN_TN2B.md`](../PLAN_TN2B.md), phần sau của TN2 trong [`../PLAN_TN1_TN3.md`](../PLAN_TN1_TN3.md).
- TN2a ([`../exp2/README.md`](../exp2/README.md)) cho TX D-PHY của AMD phát burst vào hai RX D-PHY. Chưa có packet
  CSI-2, chưa có controller CSI-2.
- TN2b phát frame RAW10 từ CSI-2 TX Subsystem 2.2 của AMD (controller CSI-2 cộng D-PHY TX bên trong), qua pad, vào
  hai đường nhận CSI-2 đầy đủ:
  - **R-X (mốc):** CSI-2 RX Subsystem 6.0 có D-PHY, cấu hình như build của board;
  - **R-F (của mình):** `IBUFDS_DPHY` → `ftel_dphy_rx` (RTL ASIC của `logical/`, không sửa) → CSI-2 RX Subsystem 6.0
    không PHY (`C_INC_PHY` = false). Đây là đường của prototype.
- Đây là lần đầu PPI của `ftel_dphy_rx` đi vào controller CSI-2 của AMD.

README này là ghi chép kỹ thuật của nhóm. Tài liệu cho team FPGA (`TN2_DESCRIPTION.md`, `TN2_REPORT.md`) sẽ viết
sau, phủ cả TN2a và TN2b.

## Tóm tắt (2026-10-26)

- **Phương án A đã làm** (§6.6, [`../PLAN_TN2B_GATE.md`](../PLAN_TN2B_GATE.md)). Khối FPGA
  [`../rtl/m_ftel_ppi_act_gate.sv`](../rtl/m_ftel_ppi_act_gate.sv) giữ `rxactivehs` vào R-F ở 0 tới `rxsynchs`. Khối có
  6 flip-flop với 4 lane, không thêm trễ, và RTL ASIC không đổi. Nó thay shim mode 3 của TB trong mọi run `SH_*`.
  - 31 run `SH_*` chạy lại qua khối: mọi kịch bản PASS; khối trùng model của TB ở 436 865 byte clock.
  - Mọi CSV và `frames.txt` của 39 run cũ trùng từng byte với bản chạy bằng shim mode 3 (282/282 file).
  - E2b-9 mới (lỗi SoT sync ở một lane): controller không treo, và các frame sau đúng từng pixel. Frame có lỗi mất hai
    line, trong đó một line sai vẫn ra `video_out`; ISR có cờ CRC (§6.6).
  - `evidence`: **PASS (12/12 checks)**; `evselftest`: **PASS** (20 ca, §7).
- Bộ so và bộ giải mã kiểm thêm timing ở PPI (`rxsynchs` đúng chỗ, lệch lane ≤ 6 byte clock), do tester team FPGA
  tìm ra lỗ hổng ([`../PLAN_CHECK_C6_C10.md`](../PLAN_CHECK_C6_C10.md)). Mọi run đều đạt.

Tóm tắt ngày 2026-10-23, trước khi có khối chỉnh:

- **Phát hiện: controller CSI-2 của AMD (không PHY) không nhận PPI của `ftel_dphy_rx` như hiện nay** (§6.1).
  - R-X ra đúng từng pixel ở mọi run. PPI của `ftel_dphy_rx` mang đúng từng packet như PPI của D-PHY AMD, nhưng R-F
    không ra line nào và đếm 0 packet.
  - Nguyên nhân nằm ở đầu mỗi burst. `ftel_dphy_rx` nâng `rxactivehs` trước `rxsynchs` 7–20 byte clock tuỳ rate,
    và `rxsynchs` lên cùng byte đầu (HAS C6, cũng là yêu cầu của team CSI). D-PHY của AMD nâng hai tín hiệu cùng lúc,
    byte đầu ở cycle sau. Controller của AMD cần `rxactivehs` không lên trước `rxsynchs`.
  - Theo HAS thì đây không phải lỗi RTL, mà là lệch hợp đồng PPI với controller của AMD (FP-8 của plan prototype).
    Ba phương án A/B/C (§6.1) chờ bạn quyết.
- **Khi testbench giữ `rxactivehs` vào R-F tới `rxsynchs`** (`+PPI_AMD_TIMING=3`, không thêm trễ, run `SH_*`):
  - 27/27 run PASS cho cả hai RX: 14 kịch bản, ở 4 rate 260 / 800 / 1440 / 1500 Mb/s; 2 và 1 lane active không cần
    build lại; ±400 ppm; RX bật muộn; tắt rồi bật lại luồng; cộng 13 run sau `afe_model`;
  - 3 phép thử âm FAIL đúng chỗ đã cài.
- `tn2b_evidence.py evidence`: **PASS (11/11 checks)**; `evselftest`: **PASS** (14 ca, §7).

## 1. Mục đích

TN2b trả lời bốn câu hỏi của `../PLAN_TN2B.md` §1 (kết quả ở §6.2):
1. Frame RAW10 do TX SS phát có ra đúng từng pixel ở `video_out` của cả R-X lẫn R-F không? Thanh ghi lỗi của cả ba
   subsystem có sạch không?
2. Controller CSI-2 của AMD có nhận PPI của `ftel_dphy_rx` giống PPI từ D-PHY của AMD không: cùng chuỗi packet, cùng
   bộ đếm, cùng trạng thái lỗi? Riêng hai trường hợp: byte clock chưa chạy lúc cấu hình RX, và byte trailer ở
   260 Mb/s.
3. Chuỗi cấu hình theo driver và example của AMD có chạy khi chưa có byte clock không? TN3 phải theo thứ tự nào?
4. Cấu hình nào của ba subsystem chạy được, để ghi vào TN3?

## 2. Sơ đồ

```
axis_vid_gen: frame tổng hợp RAW10 (§4), 4 pixel/clock ──► frames.txt
  │ AXI4-Stream video ──► tx_axis.csv
  ▼
xtxss: CSI-2 TX SS 2.2 (controller ──PPI──► tx_ppi.csv ──► D-PHY MASTER bên trong, continuous clock)
  │ pad, hai bản, đều strong
  ├───────────────────────────────┬───────────────────────────────────────────────┐
  ▼                               ▼                                               ▼
xrxss (R-X): RX SS 6.0 có PHY   IBUFDS_DPHY (+AFE=xil, mặc định)              afe_model (TN1):
  cổng theo dõi PPI               │  ┌──────────────────────── +AFE=model;     line state, term_en
  ──► xil_ppi.csv                 ▼  ▼
  │                             m_ftel_dphy_rx_wrap (RTL ASIC)
  │                               │ PPI ── +PPI_CORRUPT, +PPI_XFILL, +PPI_SOTSYNCERR (TB)
  │                               │ rxactivehs: m_ftel_ppi_act_gate (fpga/rtl/, +PPI_ADAPTER=1, run SH_*)
  │                               │             hoặc +PPI_AMD_TIMING (TB, chẩn đoán) ──► ftel_ppi.csv
  │                               ▼
  │                             xrxss_np (R-F): RX SS 6.0 không PHY
  ▼ video_out ──► xil_axis.csv    ▼ video_out ──► ftel_axis.csv
  └──── so từng pixel với golden (§4.2); thanh ghi của ba subsystem qua ba AXI4-Lite master ────┘

Check trong bench: đầu ra LP của các buffer trong D-PHY của R-X và của các buffer trước ftel_dphy_rx trùng nhau ở mọi
lần đổi sau 2,5 ps.
```

Mô phỏng chạy trong XSIM của Vivado 2025.2, part xcvp1902.

## 3. Các khối

**Ba subsystem** (tạo bởi [`exp2b.tcl`](exp2b.tcl), mỗi rate một build, 4 lane). `exp2b.tcl` in một dòng `EXP2B` với
tham số của từng IP; check `config` (§7) so các dòng đó với bảng dưới.

| IP | Module | Cấu hình |
|---|---|---|
| CSI-2 TX SS 2.2 | `xtxss` | 4 lane, RAW10, 4 pixel/clock, `C_CSI_MAX_BPC` 10, AXI4S, Active Lanes, CRC, `C_HS_LINE_RATE` = rate, `C_INC_PHY` true (D-PHY MASTER bên trong), `SupportLevel` 1. Còn lại mặc định: line buffer 2048, `C_EN_REG_BASED_FE_GEN` false, LPX 50 ns, không deskew |
| CSI-2 RX SS 6.0 có PHY | `xrxss` (R-X) | Như build của board: 4 lane, RAW10, 4 pixel/clock, `CSI_BUF_DEPTH` 16384, CRC, Active Lanes, lọc user data type, VFB với `VFB_TU_WIDTH` 96, `SupportLevel` 1; thêm `C_EN_RXPPI_AS_MON` (cổng theo dõi PPI); `DPY_LINE_RATE` = `C_HS_LINE_RATE` = rate |
| CSI-2 RX SS 6.0 không PHY | `xrxss_np` (R-F) | Như R-X, nhưng `C_INC_PHY` false, không có cổng theo dõi |

HS settle do IP tự chọn theo rate (`C_HS_SETTLE_NS`): 173 ns ở 260 Mb/s, 147 ns ở 800, 141 ns ở 1440 và 1500. Ở
1440 Mb/s, 141 ns trùng build của board. `C_INIT` của D-PHY trong RX là 100 µs.

**Nối R-F** theo `../PLAN_TN2B.md` §4.3:
- byte clock của `ftel_dphy_rx` vào `rxbyteclkhs_in`;
- `core_clk` 200 MHz chung với `dphy_clk_200M` của R-X và R-F;
- `cl_enable`, `dl_enable` do controller lái (TN1 buộc bằng 1);
- dữ liệu, `rxvalidhs`, `rxactivehs`, `rxsynchs`, `stopstate`, các cờ lỗi, ULPS và escape đi thẳng sang các chân cùng
  tên;
- `forcerxmode` buộc 0.

**Generator** ([`axis_vid_gen.sv`](axis_vid_gen.sv)):
- frame tổng hợp theo §4.1, 4 pixel mỗi beat (pixel k ở `tdata[10k+9:10k]`), tôn trọng `tready`;
- `tuser` như example của TX SS: [0] SOF ở beat đầu frame, [32:1] data type (0x2B), [63:48] word count của line;
  `tlast` ở beat cuối mỗi line; `tdest` 0 (VC 0);
- ghi `frames.txt` trước beat đầu của mỗi frame.

**Monitor:**
- [`axis_csv_mon.sv`](axis_csv_mon.sv): CSV dạng ILA, một dòng cho mỗi clock có `tvalid`. Ở hai `video_out` có thêm
  các trường `tuser`: frame, line, WC, DT. **Không có cột packet error:** với dữ liệu pixel, frame buffer (VFB) của RX
  SS 6.0 đặt `tuser[15:1]` = 0, và cờ lỗi từ controller chỉ dùng để kết thúc line (§6.4).
- [`../exp1/ppi_csv_mon.sv`](../exp1/ppi_csv_mon.sv), dùng lại: ba capture PPI. Một trên cổng theo dõi của R-X, một
  trên PPI vào R-F, một trên PPI giữa controller và D-PHY bên trong TX SS (`tx_ppi.csv`).

**AXI4-Lite master** ([`axil_bfm.sv`](axil_bfm.sv)): `wr`, `rd`, `poll`, mỗi bắt tay có giới hạn thời gian, kiểm
`resp`. Ba instance: TX, R-X, R-F. Mỗi truy cập in một dòng `TB AXIL`.

**Testbench** ([`tb_exp2b.sv`](tb_exp2b.sv)):
- **Lấy từ [`../exp1/tb_exp1.sv`](../exp1/tb_exp1.sv):** front end của RX mình (`IBUFDS_DPHY`, mux `+AFE`), nguyên
  văn; front check, khác đúng dòng đường dẫn (nay so với buffer trong D-PHY của R-X); instance wrap, khác đúng 6 dòng
  của bảng nối. Check `copy` (§7) kiểm đúng các dòng khác này ở mỗi lần kiểm chứng.
- **Thứ tự cấu hình:**
  - RX theo driver của AMD: soft reset, chờ `CSR[0]`, active lanes, nhả soft reset, `GIER`, enable;
  - TX như example của TX SS: active lanes, `CCR` = 1 (enable, `CCR[4]` = 0 tức continuous clock), chờ `CCR[2]`
    (core ready), rồi phát video ngay;
  - mặc định RX được cấu hình trước khi TX chạy, như example camera của AMD, tức lúc chưa có byte clock.
- **Clock:** `core_clk` 200 MHz (hai RX và `ftel_dphy_rx`), `core_clk` riêng 200 MHz của TX, `s_axis_aclk` của TX
  200 MHz (cũng là clock AXI4-Lite của TX, như example), `video_aclk` của hai RX 250 MHz, `lite_aclk` 50 MHz.
- **Can thiệp trên PPI vào R-F** (trước monitor, nên `ftel_ppi.csv` ghi đúng thứ R-F nhận):
  - `+PPI_CORRUPT=<lane>,<packet>,<byte>,<bit>`: lật một bit (phép thử âm). Packet đếm burst của lane đó từ 0, byte
    đếm byte của burst từ 0;
  - `+PPI_XFILL=1` (chẩn đoán): bit X/Z của `rxdatahs` thành 0;
  - `+PPI_AMD_TIMING=1|2|3` (chẩn đoán, §6.1): dời đầu burst về phía D-PHY của AMD:

    | Mode | `rxsynchs` | `rxactivehs` | Dữ liệu, `rxvalidhs` |
    |---|---|---|---|
    | 0 (mặc định) | cùng byte đầu (HAS C6) | sớm hơn `rxsynchs` (7 byte clock ở 260 Mb/s, 19–20 ở 1440) | như `ftel_dphy_rx` |
    | 1 | trước byte đầu 1 cycle | từ `rxsynchs` | trễ 1 cycle |
    | 2 | trước byte đầu 1 cycle | sớm như mode 0 | trễ 1 cycle |
    | 3 | cùng byte đầu (như mode 0) | từ `rxsynchs` | như mode 0 |

    Mode 3 là thay đổi nhỏ nhất làm R-F nhận được: mỗi lane một flop và một cổng, không thêm trễ.
  - `+PPI_ADAPTER=1` (từ 2026-10-26, mọi run `SH_*`): `rxactivehs` vào R-F lấy từ khối FPGA
    [`../rtl/m_ftel_ppi_act_gate.sv`](../rtl/m_ftel_ppi_act_gate.sv) (phương án A, [`../PLAN_TN2B_GATE.md`](../PLAN_TN2B_GATE.md)).
    Luật của khối như mode 3: `rxactivehs` từ `rxsynchs` đầu tiên tới hết burst. Khối có reset synchronizer riêng
    (2 flop `ASYNC_REG`), nối cùng reset với `ftel_dphy_rx`. TB có model riêng của luật đó, so với khối ở mọi byte
    clock và in `TB ADAPTER CHECK: comparisons N, differences D`. Không dùng chung với `+PPI_AMD_TIMING`;
  - `+PPI_SOTSYNCERR=<lane>,<packet>` (E2b-9): ở burst đó của lane đó, bỏ `rxsynchs` và `rxvalidhs`, đặt
    `errsotsynchs` vào chu kỳ của `rxsynchs`. Đó là PPI của `ftel_dphy_rx` sau một lỗi SoT sync (HAS C8). Khối
    giữ `rxactivehs` của burst đó ở 0. Run kết thúc khi 30 µs không RX nào ra line.
- **Dòng kết quả:** `TB DONE`, `TB FRONT END CHECK`, `AFE`, `TB FTEL CFG` như TN1; thêm `TB REG` (thanh ghi của ba
  subsystem ở cuối run), `TB AXIS` (beat, line, frame của ba luồng), `TB TX` (khởi động TX, lúc controller xin HS
  clock, lúc mỗi RX thấy HS), `TB RX CFG` (lúc mỗi RX được cấu hình), `TB CORRUPT`, `TB DIAG`, `TB ADAPTER`,
  `TB SOTSYNCERR`, `TB AXIL`.
- Danh sách plusarg nằm ở đầu file.

**Chạy và kiểm** ([`run_exp2b.sh`](run_exp2b.sh), [`tn2b_evidence.py`](tn2b_evidence.py)):
- mỗi run copy thư mục XSIM của build sang thư mục riêng. Hai run chung một thư mục thì run sau chạy với plusarg của
  run trước (lỗi đã gặp ở S2);
- `rss.txt` ghi bộ nhớ của `xsimk` mỗi 10 s;
- `check.txt`: các lệnh `csi2_dump.py` của plan §2.3. Một phép so chỉ đạt khi hai bên có cùng số line hoặc packet,
  vì `csi2_dump.py compare` không tự kiểm điều này;
- `tbcheck.txt`: `tn2b_evidence.py tbcheck`. Run PASS khi cả hai file PASS.

**Dùng lại, không sửa:** `../exp1/` (`afe_model.sv`, `ppi_csv_mon.sv`, `cfg_for_rate.py`, model cấu hình qua
`tn1_evidence.py`), `../exp2/tn2a_evidence.py` (`code_lines`, `block`), RTL `logical/` và `config/`.
`../tools/csi2_dump.py` có thêm timing ở PPI ngày 2026-10-26 ([`../PLAN_CHECK_C6_C10.md`](../PLAN_CHECK_C6_C10.md)).

## 4. Dữ liệu vào, golden và cách so

### 4.1 Dữ liệu vào

Frame **tổng hợp**, do `axis_vid_gen` sinh theo công thức. Không phải ảnh mẫu, không phải frame camera: chưa có
capture camera nào, và với công thức thì mỗi pixel mang vị trí của nó, nên lệch, đảo lane, lẫn line hay mất line đều
lộ ra kèm vị trí.

RAW10 (0x2B), VC 0. Trên dây TX SS đóng gói 4 pixel thành 5 byte (CSI-2 v1.3 §11.4.4); RX SS mở gói ở `video_out`.

| Pattern | Pixel p(f, y, x) | Bắt được gì |
|---|---|---|
| `counter` | (x + 37·y + 101·f) mod 1024 | lệch hay đổi chỗ pixel, lẫn line, lẫn frame |
| `prbs` | 10 bit liên tiếp của LFSR x¹⁵ + x¹⁴ + 1, seed 1 + f·H + y | lỗi phụ thuộc dữ liệu |
| `synclike` | lặp 0x2E0 0x2E0 0x000 0x000 0x3FF 0x3FF 0x155 0x2AA | byte 0xB8 (giống sync), chuỗi 0x00/0xFF, 0x55/0xAA |

### 4.2 Golden

Ba bản phải trùng nhau trước, rồi mới so hai RX với chúng:
1. công thức, viết lại riêng trong `tn2b_evidence.py`;
2. `frames.txt`: những gì generator đưa ra;
3. `tx_axis.csv`: những beat TX SS thực sự nhận (`tvalid` và `tready`).

### 4.3 So cái gì

| Điểm đo | So với | Công cụ |
|---|---|---|
| `video_out` của R-X, R-F | golden, từng pixel, từ SOF đầu tiên sau khi RX được cấu hình | `csi2_dump.py compare axis`; `tn2b_evidence.py decode` |
| PPI của TX, R-X, R-F | không lỗi ECC/CRC; packet của TX = R-X = R-F; payload sau khi mở gói = golden | `csi2_dump.py ppi`, `compare ppi`; `decode` |
| Thanh ghi (`TB REG`) | R-F với R-X; image info với kích thước frame; cờ lỗi | `tbcheck` |

Chuẩn: từng pixel bằng nhau tuyệt đối, đúng số line, mỗi frame đúng một SOF, đúng thứ tự frame.

## 5. Các test

Mặc định: 2 frame 640 × 16 (WC 800 byte), `counter`, 1440 Mb/s, 4 lane.

| ID | Rate, lane | Tham số | Mục đích |
|---|---|---|---|
| E2b-1 | 1440, 4 | mặc định | Cơ bản |
| E2b-2a / 2b | 1440, 4 | `+PATTERN=prbs` / `synclike` | Payload ngẫu nhiên; payload có byte giống sync |
| E2b-2c | 1440, 4 | `+WIDTH=3840 +HEIGHT=8` | Line dài cỡ sensor 4K (WC 4800) |
| E2b-3 | 1440, 4 | `+FRAMES=8 +WIDTH=64 +HEIGHT=4` | FS/FE dày, packet sát nhau |
| E2b-4a/b/c | 260 / 800 / 1500, 4 | như E2b-1 (260: `+TIMEOUT_US=8000`) | Rate thấp nhất, rate bring-up TN3, rate cao nhất R1 |
| E2b-5a/b | 1440, 4 (build); 2 / 1 lane active | `+LANES_ACTIVE=2` / `1` | Đổi số lane không cần build lại |
| E2b-6 | 1440, 4 | `+FRAMES=4 +RX_LATE=1` | RX được cấu hình giữa frame 0; so từ SOF kế; thanh ghi chỉ báo cáo |
| E2b-7a/b | 1440, 4 | như E2b-3, `+CORE_HALF=2.501` / `2.499` | ±400 ppm giữa TX và hai RX |
| E2b-8 | 1440, 4 | `+FRAMES=4 +STREAM_TOGGLE=1` | Tắt rồi bật lại TX sau frame 0; thanh ghi chỉ báo cáo |
| E2b-9 (từ 2026-10-26) | 1440, 4 | `+FRAMES=3 +PPI_SOTSYNCERR=0,5` (lane 0, packet 5 = line 4 của frame 0), chỉ với khối chỉnh | Lỗi SoT sync ở một lane: controller không treo, các frame sau đúng (check `gate`); phần còn lại chỉ báo cáo |
| M_* | như trên trừ E2b-8 và E2b-9 | `+AFE=model` | RX mình sau `afe_model` |
| NEG-ecc | 1440, 4 | `+PPI_CORRUPT=0,1,0,0` (bit 0 của byte header đầu, packet 1) | ECC sửa được: chỉ thanh ghi ECC của R-F báo |
| NEG-crc | 1440, 4 | `+PPI_CORRUPT=1,1,2,3` (một bit payload) | CRC, đúng một pixel sai |
| NEG-front | 1440, 4 | `+NEG_FRONT=1` | Front check phải đếm ra khác biệt |

**Hai nhóm run** (`run_exp2b.sh`), 40 run từ 2026-10-26 (39 trước đó):
- **`SH_*`** (`run_exp2b.sh shim`, 31 run): mọi kịch bản, `M_*` và NEG. Đây là tập được chấm. Từ 2026-10-26 các run
  này dùng khối chỉnh (`+PPI_ADAPTER=1`); ngày 2026-10-23 chúng dùng shim mode 3 của TB (`+PPI_AMD_TIMING=3`).
- **Phát hiện** (`run_exp2b.sh finding`, 9 run): E2b-1, E2b-4a/b/c, E2b-6 không chỉnh PPI, và 4 run chẩn đoán
  `DBG-E2b-1-xfill`, `DBG-E2b-1-amd1..3`.

## 6. Kết quả lần chạy 2026-10-23 (lần chạy lại qua khối chỉnh ngày 2026-10-26: §6.6)

39/39 run ra đúng kỳ vọng, cùng hash nguồn `1ac03101efd59a1a`. RTL `logical/` và `config/` không đổi so với commit
`cd1f0b2`.

### 6.1 Phát hiện: đầu burst của PPI

**Hiện tượng** (5 run không chỉnh PPI, ở cả 4 rate):
- R-X PASS từng pixel;
- PPI vào R-F mang đúng chuỗi packet của R-X (`packets-xil-ftel` PASS, ví dụ 35/35 packet ở E2b-1), không lỗi
  ECC/CRC;
- nhưng R-F ra 0 line, `CSR` packet count = 0, ISR không có frame received và không có cờ lỗi nào.

**Đầu mỗi burst, đo trên capture** (`tn2b_evidence.py evidence`, check `finding`), tính bằng byte clock:

| Rate (Mb/s) | Run | `ftel_dphy_rx`: `rxactivehs` → `rxsynchs` | `ftel_dphy_rx`: `rxsynchs` → byte đầu | D-PHY AMD: `rxactivehs` → `rxsynchs` | D-PHY AMD: `rxsynchs` → byte đầu |
|---|---|---|---|---|---|
| 260 | E2b-4a | 7 | 0 | 0 | 1 |
| 800 | E2b-4b | 12 | 0 | 0 | 1 |
| 1440 | E2b-1, E2b-6 | 19–20 | 0 | 0 | 1 |
| 1500 | E2b-4c | 19–20 | 0 | 0 | 1 |

Mỗi run có 140 burst (35 packet × 4 lane; E2b-6: 284), và giá trị đúng như bảng ở mọi burst.

**Chẩn đoán** (`DBG-E2b-1-*`, 1440 Mb/s):

| Run | Thay đổi trên PPI vào R-F | `rxactivehs` → `rxsynchs` | R-F |
|---|---|---|---|
| `xfill` | bit X của `rxdatahs` (khi `rxvalidhs` = 0) thành 0 | 19–20 | 0 line |
| `amd1` | như D-PHY AMD: `rxsynchs` trước byte đầu, `rxactivehs` từ `rxsynchs` | 0 | PASS |
| `amd2` | chỉ dời `rxsynchs` lên trước byte đầu, `rxactivehs` vẫn sớm | 19–20 | 0 line |
| `amd3` | chỉ giữ `rxactivehs` tới `rxsynchs`; `rxsynchs` vẫn cùng byte đầu | 0 | PASS |

Kết luận: controller CSI-2 của AMD (không PHY) cần `rxactivehs` không lên trước `rxsynchs`. Vị trí `rxsynchs` (cùng
byte đầu, HAS C6) không phải vấn đề. Ở 29 run `SH_*` (NEG-front ngoài ra, vì ở đó PPI hỏng có chủ ý), `rxactivehs`
vào R-F lên cùng `rxsynchs` ở mọi burst.

**Vì sao không phải lỗi RTL:** HAS của mình cho phép `rxactivehs` lên trước (dòng 909: "rises at or before"
`rxsynchs`). Yêu cầu C8 của team CSI (HAS, Bảng A-2) còn dựa vào điều đó: sau lỗi sync, `rxactivehs` giữ tới EoT dù
không có `rxsynchs`. HAS docx của team CSI cũng giữ `rxactivehs` trong burst deskew. Lệch là giữa hợp đồng chung đó
và controller của AMD dùng ở prototype.

**Phương án** (đụng hợp đồng với team CSI, nên không tự chọn). Ngày 23/10, sau ma trận A 102 / B 88 / C1 74 / C0 64,
bạn chọn **A**. Khối đã làm và được kiểm từ 2026-10-26 (§6.6, `../PLAN_TN2B_GATE.md`).

| | Làm gì | Ảnh hưởng |
|---|---|---|
| **A (đã chọn)** | Khối chỉnh PPI chỉ ở FPGA, giữa `ftel_dphy_rx` và RX SS (như mode 3: mỗi lane 1 flop + 1 cổng, không trễ) | RTL ASIC và hợp đồng với team CSI giữ nguyên; prototype có thêm một khối nhỏ ngoài RTL ASIC |
| B | Thêm option trong RTL `ftel_dphy_rx` cho kiểu đầu burst của AMD | Sửa RTL ASIC, cần plan riêng và chạy lại TN1/TN2 |
| C | Thống nhất một convention với team CSI | Đụng C8/C9 trong HAS của team CSI; team CSI quyết |

### 6.2 Trả lời bốn câu hỏi của §1

1. **R-X: có**, ở mọi run. **R-F: không, với PPI như hiện nay** (§6.1). **Với PPI chỉnh ở mode 3 (23/10), rồi qua
   khối chỉnh của FPGA (26/10, §6.6): có**, 27/27 run, cả hai lần:
   từng pixel, đúng số line, mỗi frame một SOF, ở 4 rate, 1/2/4 lane, ±400 ppm, sau cả `IBUFDS_DPHY` lẫn
   `afe_model`. Thanh ghi:
   - TX: ISR = 0 ở mọi run;
   - R-X và R-F: frame received, không cờ lỗi, R-F có packet count và image info VC0 bằng R-X, ở mọi run được chấm
     (24 run; E2b-6, `M_E2b-6`, E2b-8 chỉ báo cáo, §6.3);
   - bit 27:24 trong ISR của R-F là X (§6.3, FP-6).
2. **Có, khi đầu burst được chỉnh:** cùng chuỗi packet (VC, DT, WC, payload) với R-X ở mọi run, cùng packet count,
   cùng image info, cùng cờ lỗi.
   - Byte clock chưa chạy lúc cấu hình: R-F vẫn qua được vòng chờ reset của driver ("soft reset done reached" ở
     1,1 µs), và nhận đúng sau đó. Chỉ còn bit dự trữ 27:24 của ISR là X (§6.3).
   - Trailer mỗi packet (tổng 4 lane): `ftel_dphy_rx` giữ 0 byte ở mọi rate sau `IBUFDS_DPHY`, và 0–8 byte ở
     260 Mb/s sau `afe_model`; D-PHY của AMD giữ 8 byte ở 260 Mb/s, 40 ở 800, 72–74 ở 1440–1500 (§6.5). Controller
     của AMD bỏ được cả hai.
3. **Có.** RX cấu hình trước khi TX chạy (thứ tự của example camera) chạy cho cả hai RX. RX cấu hình muộn, giữa
   frame 0 (E2b-6), cũng chạy: từ SOF kế tiếp hai RX ra đúng frame. Đề xuất cho TN3: theo thứ tự của AMD, che ISR bằng
   mặt nạ của driver (0xF07FFFFF), và nếu muốn bit dự trữ sạch thì cấu hình (hoặc soft reset) R-F sau khi clock lane
   vào HS.
4. **Cấu hình ở §3** (dòng `EXP2B` của từng build, check `config`). Đây là cấu hình ghi vào đặc tả TN3.

### 6.3 Các điểm khác (chỉ báo cáo)

- **Bit 27:24 của ISR R-F là X** ở mọi run mà R-F được cấu hình khi chưa có byte clock: 36/39 run, tức mọi run
  trừ ba run E2b-6. Ở ba run đó R-F được cấu hình khi byte clock đã chạy, và các bit này đọc ra 0. Driver của AMD không định nghĩa
  bit 27:23 (`XCSI_ISR_ALLINTR_MASK` = 0xF07FFFFF). Đây là phần FP-6 của plan prototype: byte clock của
  `ftel_dphy_rx` dừng khi clock lane không ở HS, nên phần của controller chạy theo byte clock không có cạnh clock
  trong lúc reset. R-X không gặp, vì D-PHY của AMD có byte clock ngay từ lúc khởi động.
- **E2b-8 có kiểm FP-6 thật.** TB tắt TX (`CCR` = 0) ngay khi hai RX nhận xong frame 0, chờ 20 µs rồi bật lại.
  - Clock lane rời HS: byte clock của cả hai RX dừng từ 413,2 µs tới khoảng 797 µs. Hai capture PPI không có dòng nào
    trong khoảng đó, còn capture TX vẫn liên tục.
  - TX nhận frame 1 vào line buffer ngay sau khi bật lại (SOF ở 437,2 µs), nhưng tới 797,0 µs mới phát FS của nó.
    `CCR[2]` không lên lại trong 200 lần đọc.
  - R-F vẫn ra đúng cả 4 frame.
- **TX SS chỉ gửi FE của một frame khi bắt đầu frame kế** (với `C_EN_REG_BASED_FE_GEN` mặc định false; nguyên nhân
  ⚠️ chưa đọc được trong IP, RTL TX đã mã hoá). Vì vậy frame cuối mỗi run không có FE trên cả ba PPI. Ở E2b-8 thiếu
  thêm FE của frame 0, vì TX tắt trước frame 1. R-X và R-F thấy giống nhau; ở TN3 bên phát là camera, nên điều này chỉ
  thuộc bench.
- **Thanh ghi của E2b-6 và E2b-8** (chỉ báo cáo): cả R-X lẫn R-F báo frame sync error của VC0 (frame bị cắt bởi lúc
  cấu hình muộn, hoặc thiếu FE do tắt luồng). Packet count ở E2b-6: R-X 59, R-F 60, vì hai RX cắt ở hai chỗ khác nhau
  của frame 0.

### 6.4 `tuser` ở `video_out`

`tuser[1]` luôn bằng 0 với dữ liệu pixel. Trong RTL của VFB (`vfb_v1_0`, Vivado 2025.2), đầu ra ghép thành
`{ECC/CRC, 2'b0, DT, WC, line, frame, 15'h0, SOF}`. Cờ lỗi `tuser[1]` từ controller chỉ dùng để kết thúc line, và chỉ
đi tiếp với data type user-defined. Mục "packet error" của plan (§5, NEG-crc) vì vậy không bao giờ báo được; theo lựa
chọn của bạn ngày 23/10, mục này đã bỏ khỏi monitor, TB và các check. Lỗi payload vẫn bị bắt ở ba chỗ: so pixel với
golden, CRC trên PPI, thanh ghi CRC (NEG-crc). Ở TN3, ILA trên `video_out` không tự đánh dấu được line hỏng; cần đọc
ISR hoặc bắt cả PPI.

### 6.5 Số đo theo rate

`tn2b_evidence.py report`, trên các run `SH_*` có frame của E2b-1 (min..max):

| | 260 Mb/s | 800 Mb/s | 1440 Mb/s | 1500 Mb/s |
|---|---|---|---|---|
| Run | SH_E2b-4a, SH_M_E2b-4a | SH_E2b-4b, SH_M_E2b-4b | SH_E2b-1, -2a, -2b và M_ của chúng | SH_E2b-4c, SH_M_E2b-4c |
| `init_done` của TX (µs) | 392,758 | 570,463 | 383,263 | 380,538 |
| Controller TX xin HS clock (µs; sau beat đầu, ns) | 394,585 (677) | 571,880 (268) | 384,593 (180) | 381,861 (173) |
| Trailer mỗi packet, PPI của R-X (byte, tổng 4 lane) | 8 | 40 | 72 | 72–74 |
| Trailer mỗi packet, PPI vào R-F | 0 sau `IBUFDS_DPHY`, 0–8 sau `afe_model` | 0 | 0 | 0 |
| Burst của một line trên PPI của TX (ns) | 6708 | 2300–2470 | 1400–1572 | 1349–1520 |
| Độ trễ SOF, TX → `video_out` R-X / R-F (ns) | 2926 / 3874 | 1822 / 2138 | 1654 / 1834 | 1638 / 1810 |
| R-F trễ hơn R-X (ns) | 948 | 316 | 180 | 172 |

- R-F trễ hơn R-X khoảng 31–32 byte time ở mọi rate. Con số này bằng độ trễ thêm mà TN2a đo ở PPI (950, 313–316,
  174–177, 169–172 ns), tức đến từ delay line của phần cắt trailer trong `ftel_dphy_rx`, không phải từ controller.
- Độ trễ của các line sau tăng dần (tới 26 µs ở 1440 Mb/s), vì TX nhận line ở AXI4-Stream nhanh hơn tốc độ dây và
  giữ chúng trong line buffer. Hai RX tăng như nhau.
- Bảng đủ, kèm khoảng cách giữa các burst trên PPI của TX, nằm trong output của `report`.

**Máy:** mỗi run 121–252 s, bộ nhớ `xsimk` 2,4–3,8 GB (E2b-8: 5,1 GB). Ngày 23/10, 4 build chỉ phải compile lại
(khoảng 16 s, chạy song song), và 39 run chạy 3 luồng xong trong 35 phút (tổng thời gian các run 6 038 s).

### 6.6 Chạy lại qua khối chỉnh, và E2b-9 (2026-10-26)

**Cách chạy:**
- 4 build làm lại, vì `exp2b.tcl` thêm file của khối: mỗi build khoảng 50 s.
- `shim` (31 run, có E2b-9) và `finding` (9 run), 3 luồng, 34 phút. Tổng thời gian các run 6 275 s; mỗi run 121–253 s;
  tối đa 5,1 GB (E2b-8).
- 39 run cũ được chép sang `work/exp2b/_pre_gate/` trước khi chạy.

**Hồi quy so với shim mode 3** (39 run cũ):
- mọi CSV và `frames.txt` trùng từng byte (282/282 file);
- `check.txt` trùng từng byte;
- `tb.txt` chỉ khác dòng `TB ADAPTER` / `TB DIAG`.

Vậy khối cho đúng thứ mode 3 đã cho ở mọi burst. Trường hợp duy nhất hai cách khác nhau là hai burst cách nhau 1 cycle;
TN2b không gặp trường hợp đó.

**E2b-9** (lane 0, packet 5 = line 4 của frame 0; 3 frame; 152 s):

| | Kết quả |
|---|---|
| PPI vào R-F | Lane 0 có 52 burst, lane 1–3 có 53. `errsotsynchs` một lần, trong packet 5 của các lane khác, lúc `rxactivehs` của lane 0 = 0 |
| R-X | 48/48 line, ISR sạch |
| R-F, frame 1 và 2 | Trùng golden từng pixel, đúng WC và RAW10 ở mọi line: **controller phục hồi**, không treo |
| R-F, frame 0 (chỉ báo cáo) | 15 line: 14 line đúng (0–3, 6–15); không có line 4 và 5; thay vào đó 1 line lẫn: byte của lane 0 là của line 5, byte của lane 1–3 là 17 byte đầu của line 4 rồi phần còn lại của line 5 |
| ISR của R-F (chỉ báo cáo) | Frame received, VC0 frame level (bit 0), CRC (bit 9); không có bit SoT sync (bit 12), dù PPI có `errsotsynchs`. Packet count R-F 47, R-X 48 |

- **Cái giá của một lỗi sync ở một lane là hai line,** và một trong hai line là line sai vẫn được đưa ra. Cờ CRC chỉ
  có ở ISR. `video_out` không đánh dấu line đó, vì `tuser[1]` luôn bằng 0 (§6.4).
- ⚠️ Cách đọc, chưa kiểm: FIFO mỗi lane của controller sâu khoảng 18 phần tử. Lane 0 thiếu burst nên FIFO của lane 1–3
  đầy, mất đuôi packet 5 và đầu packet 6, và hai packet bị ghép thành một.
- 🔍 Chưa biết D-PHY của AMD xử lý lỗi sync ra sao (TN2b không cài được lỗi đó vào line của TX AMD).
- Quy tắc khác cho burst lỗi sync (nâng `rxactivehs` cùng `errsotsynchs`) chưa thử: chờ bạn quyết có cần so không.

## 7. Kiểm chứng: vì sao tin được kết quả

[`tn2b_evidence.py`](tn2b_evidence.py) kiểm lại tự động từ output trong `fpga/work/exp2b`:

```bash
fpga/exp2b/run_exp2b.sh evidence       # mỗi check một dòng PASS/FAIL, rồi EVIDENCE: PASS/FAIL
fpga/exp2b/run_exp2b.sh evselftest     # script kiểm chứng tự thử trên lỗi cài sẵn (§7.2)
python3 fpga/exp2b/tn2b_evidence.py selftest   # bộ giải mã tự thử trên giá trị đã biết
```

Kết quả ngày 2026-10-23: **EVIDENCE: PASS (11/11 checks)**. Ngày 2026-10-26, trên 40 run của lần chạy lại qua khối
chỉnh: **EVIDENCE: PASS (12/12 checks)**, có thêm check `gate`.

| Check | Kiểm gì | 2026-10-23 (shim mode 3) | 2026-10-26 (khối chỉnh) |
|---|---|---|---|
| `checker` | Selftest của `csi2_dump.py` | PASS | PASS |
| `decode` | Giải mã lại mọi capture bằng bộ giải mã riêng của `tn2b_evidence.py` (không chung code với `csi2_dump.py`; ECC sửa 1 bit như receiver); từ 26/10 cả timing ở PPI (C6, C10); mỗi mục của `check.txt` phải cùng kết luận; `frames`, `tx-axis`, `golden-ppi` (ba golden trùng nhau, PPI của TX và R-X trùng golden) đạt ở mọi run; selftest của bộ giải mã (15 ca: ví dụ CRC/ECC của CSI-2 v1.3, so ngẫu nhiên với `csi2_dump.py`, capture giả) | 270/270 mục, 39 run | 277/277 mục, 40 run |
| `runs` | Đủ mọi run; mọi run `TB DONE OK`; mọi kịch bản `SH_*` PASS cả `check.txt` lẫn `tbcheck` (SH_E2b-9: `tbcheck`; `check.txt` của nó hỏng ở R-F theo thiết kế, xét ở `gate`) | 39/39 | 40/40 |
| `regs` | Ở mọi kịch bản `SH_*` được chấm: hai RX frame received, không cờ lỗi, R-F bằng R-X; liệt kê run chỉ báo cáo và bit X | 24 run chấm, 3 run báo cáo | 24 run chấm, 4 run báo cáo (thêm SH_E2b-9) |
| `front` | Đầu ra LP của hai bộ buffer trùng nhau ở mọi lần đổi sau 2,5 ps; RX mình sau `IBUFDS_DPHY` trừ khi `+AFE=model` | 38 run, 6 770 088 lần so, 0 khác; 13 run sau `afe_model` | 39 run, 6 995 053 lần so, 0 khác; 13 run sau `afe_model` |
| `afe` | `term_en` không trễ, không thiếu (NEG-front xem `neg`) | 38/38 | 39/39 |
| `config` | Cấu hình RX mình đúng model HAS ở rate đó; tham số ba subsystem ở 4 build đúng §3 | 39 run, 4 build | 40 run, 4 build |
| `sources` | Hash nguồn trong `args.txt` từng run bằng hash nguồn hiện tại (RTL theo `filelist.f`, `exp1/afe_model.sv`, `exp1/ppi_csv_mon.sv`, từ 26/10 `rtl/m_ftel_ppi_act_gate.sv`, `exp2b/*.sv`) | 39/39, `1ac03101efd59a1a` | 40/40, `ce12047cbce523a4` |
| `copy` | Ba khối lấy từ `tb_exp1.sv` khác đúng các dòng đã liệt kê (0, 1 và 6 dòng) | 29, 15, 59 dòng code | 29, 15, 59 dòng code |
| `neg` | NEG-ecc: bit cài rơi vào header, được sửa; `check.txt` đạt; chỉ R-F báo ECC 1 bit; `regs` là mục duy nhất của `tbcheck` hỏng. NEG-crc: pixel sai duy nhất của R-F đúng là pixel mà bit cài thuộc về (frame 0, line 0, pixel 4: 0x024 thay cho 0x004), chỉ R-F báo CRC, `check.txt` hỏng đúng `pixels-ftel`, `ppi-ftel`, `packets-xil-ftel`. NEG-front: front check đếm ra khác biệt, R-X vẫn đạt | 3/3 đúng chỗ | 3/3 đúng chỗ |
| `finding` | §6.1: 5 run không chỉnh đúng dấu hiệu (R-X đạt, PPI vào R-F = PPI R-X, R-F 0 line, 0 packet; `rxactivehs` sớm ở mọi burst; D-PHY AMD cùng lúc); 4 run chẩn đoán đúng quy luật; mọi run `SH_*` (trừ NEG-front) có `rxactivehs` cùng `rxsynchs` | đúng, 29 run `SH_*` | đúng, 30 run `SH_*` |
| `gate` (từ 26/10) | Mọi run `SH_*` lấy `rxactivehs` từ khối, trùng model của TB ở mọi byte clock. SH_E2b-9: chỉ burst đã định bị đổi; trong `ftel_ppi.csv` lane 0 ít hơn một burst và có `errsotsynchs` lúc `rxactivehs` của nó = 0; R-X đạt; R-F ra đúng các frame sau frame lỗi và run kết thúc (§6.6) | — | 31 run, 436 865 byte clock, 0 khác; SH_E2b-9 đúng chỗ, R-F phục hồi |

### 7.1 Theo các lớp của plan §7

1. **Tín hiệu vào:** ba golden trùng nhau ở mọi run; TX SS và R-X là IP của AMD, và R-X đạt ở mọi run.
2. **Bộ kiểm biết báo FAIL:** selftest của `csi2_dump.py` và của bộ giải mã; ba NEG FAIL đúng chỗ, NEG-crc tới từng
   pixel; `evselftest` (§7.2).
3. **PASS tính đúng:** bộ giải mã riêng cho cùng kết luận với `check.txt` ở mọi mục. `run_exp2b.sh recheck` (30 s,
   không mô phỏng) viết lại 78 file: 39 `check.txt` không đổi; 9 `tbcheck.txt` chỉ đổi chữ ở dòng `axis` (ba run đầu
   của mỗi luồng xong trước khi `tbcheck` bỏ chữ "with packet error"; dựng lại dòng cũ thì trùng hash đã lưu), kết
   luận không đổi. Ngày 26/10, trên 40 run của lần chạy lại: 31 s, 80 file viết lại trùng từng byte với bản trước.
4. **Thứ được test là thứ trong repo:** hash nguồn theo từng run; check `copy`.
5. **Không nhờ may:** 4 rate, ±400 ppm, line dài, nhiều frame, ba pattern.
6. **Cùng front end:** front check ở mọi run, có phép thử âm.
7. **Controller thấy hai PHY như nhau** (khi đầu burst được chỉnh): chuỗi packet và thanh ghi của R-F bằng R-X ở mọi
   run.

### 7.2 Kiểm chính `tn2b_evidence.py`

`evselftest` chạy `evidence` trên các run thật, mỗi lần cài một lỗi; các run được link vào thư mục tạm, chỉ run bị
sửa được chép sang rồi mới sửa (của build thì chỉ chép file bị sửa). Mỗi lỗi phải làm hỏng đúng các check ghi dưới.
Ngày 23/10 cả 14 ca đúng (`evselftest: PASS`, 7,5 s). Ngày 26/10 cả 20 ca đúng (`evselftest: PASS`, 8,7 s), trên 40
run của lần chạy lại. `checker` không có ca cài lỗi, vì bản thân nó là selftest của `csi2_dump.py`.

| Lỗi cài | Check phải hỏng |
|---|---|
| Không lỗi | không check nào |
| Đảo 1 bit của một pixel trong `ftel_axis.csv` (SH_E2b-1) | `decode` |
| Bỏ một line khỏi `xil_axis.csv` | `decode` |
| Đảo 1 bit payload trong `ftel_ppi.csv` | `decode` |
| `rxsynchs` High 3 cycle trong `ftel_ppi.csv` (lỗi tester team FPGA cài, thêm 26/10) | `decode` |
| `rxsynchs` dời tới byte payload thứ ba (như trên). Nó cũng mở khoảng `rxactivehs` → `rxsynchs` mà check `finding` thấy | `decode`, `finding` |
| Cả lane 3 trễ 8 cycle (như trên) | `decode` |
| Bật bit CRC trong ISR của R-F (`tb.txt`) | `regs`, `runs` |
| Một khác biệt front end | `front`, `runs` |
| Một `term_en` trễ | `afe`, `runs` |
| `eot_skip_bytes` khác model | `config` |
| `VFB_TU_WIDTH` khác trong `vivado.out` của build 1440 | `config` |
| Hash nguồn khác | `sources` |
| Thiếu run SH_E2b-3 | `runs` |
| Đổi bit cài của NEG-crc trong `args.txt` | `neg` |
| R-F đếm packet ở run không chỉnh (E2b-1) | `finding` |
| Sửa một dòng của instance wrap trong `tb_exp2b.sv` | `copy` |
| Khối chỉnh khác model 1 lần (`tb.txt` của SH_E2b-1, thêm 26/10) | `gate`, `runs` |
| Đảo 1 bit của pixel đầu frame 1 của R-F trong SH_E2b-9 | `gate` |
| `rxactivehs` của lane 0 lên trong burst có lỗi sync (SH_E2b-9), như khi không có khối | `gate`, `finding` |

### 7.3 Giới hạn

1. **TX SS, R-X, R-F và front end là model mô phỏng của AMD,** không phải phần cứng. RTL của controller đã mã hoá:
   quy luật đầu burst (§6.1) được tìm bằng thử, không đọc từ RTL.
2. **Khối chỉnh của phương án A đã viết và mô phỏng** (`../rtl/`, từ 2026-10-26): unit TB, lint, luật, synth OOC
   trên part của board, rồi trong mọi run `SH_*`. Nó vẫn chưa chạy trên board (TN3), và RTL của `ftel_dphy_rx` chưa
   được synth bằng Vivado (mục mở của `../PLAN_TN2B_GATE.md`).
3. **RTL mô phỏng zero-delay,** không có metastability. CDC của các ngõ ra không đồng bộ của RX mình (FP-5) thuộc
   TN2c và TN3.
4. **Một controller TX, một kiểu frame** (RAW10, VC 0, continuous clock).

**Độ tin cậy:**
- HIGH: PASS và phát hiện là thật trong điều kiện đã mô phỏng; quy luật "`rxactivehs` không lên trước `rxsynchs`"
  (cả 4 rate, 4 run chẩn đoán, 30 run `SH_*`); `tuser[1]` = 0 (đọc RTL của VFB); bit 27:23 không được driver định
  nghĩa (header của driver).
- MED: nguyên nhân FE chỉ gửi khi có frame kế (quan sát chắc, nguyên nhân là đoán); controller AMD trên silicon xử lý
  đầu burst như model.
- LOW: chuyển kết luận sang board khi chưa có TN3.

## 8. TN2b không kiểm

- Frame camera thật và ảnh mẫu (chưa có capture).
- CDC và metastability (FP-5): TN2c, TN3.
- Bản FPGA của RX mình (TN2c).
- Non-continuous clock, ULPS, escape, deskew, nhiều VC, data type khác RAW10, embedded data.
- Hiệu ứng board, analog, skew (TN1 đã phủ ±0,2 UI).
- 400, 600, 1000, 1200 Mb/s ở mức CSI-2 (mức PHY có ở TN2a).

## 9. Cách chạy

Chạy từ thư mục gốc của repo. Output ở `fpga/work/exp2b/<tên>/` (gitignored): `frames.txt`, `tx_axis.csv`,
`xil_axis.csv`, `ftel_axis.csv`, `tx_ppi.csv`, `xil_ppi.csv`, `ftel_ppi.csv`, `xsim.log`, `tb.txt`, `args.txt`,
`rss.txt`, `check.txt`, `tbcheck.txt`.

```bash
fpga/exp2b/run_exp2b.sh build 1440        # ba subsystem, project, compile, elaborate (Vivado ~40 s, compile lại ~16 s)
fpga/exp2b/run_exp2b.sh E2b-1             # cơ bản, không chỉnh PPI (phát hiện §6.1)
fpga/exp2b/run_exp2b.sh shim              # 31 run SH_*: all (cả E2b-9), model, neg qua khối chỉnh (+PPI_ADAPTER=1)
fpga/exp2b/run_exp2b.sh shim E2b-4 a      # một phần, có chỉnh
fpga/exp2b/run_exp2b.sh shim E2b-9        # lỗi SoT sync ở lane 0 của packet 5
fpga/exp2b/run_exp2b.sh finding           # 9 run của phát hiện
fpga/exp2b/run_exp2b.sh run 1440 <tên> +PATTERN=prbs +FRAMES=4   # một kịch bản tự chọn
fpga/exp2b/run_exp2b.sh summary           # dòng kết quả của mọi run
fpga/exp2b/run_exp2b.sh recheck           # kiểm lại mọi output bằng công cụ hiện tại, không mô phỏng
fpga/exp2b/run_exp2b.sh evidence          # kiểm chứng (§7)
fpga/exp2b/run_exp2b.sh evselftest        # thử chính script kiểm chứng trên các lỗi cài sẵn (§7.2)
fpga/rtl/run_rtl.sh all                   # khối chỉnh: lint, luật, unit TB, synth OOC (../rtl/)
python3 fpga/exp2b/tn2b_evidence.py report      # số đo theo rate (§6.5)
EXP2B_DEBUG=typical fpga/exp2b/run_exp2b.sh run 1440 DBG-x +VCD=1   # build có debug, ghi tn2b.vcd
```

- **Song song:** các run cùng build chạy song song được, vì mỗi run có bản copy thư mục XSIM riêng; build thì không
  được chạy cùng lúc với run trên chính build đó. Trước khi chạy 3 luồng, kiểm RAM trống (mỗi run tới 5 GB).
- Danh sách plusarg nằm ở đầu [`tb_exp2b.sv`](tb_exp2b.sv).
