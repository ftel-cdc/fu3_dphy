# Plan: TN2b — frame RAW10 qua CSI-2 TX Subsystem của AMD vào hai đường nhận CSI-2, mô phỏng XSIM (2026-10-22)

> Repo `fu3_dphy`, branch `dev`, sau commit `cd1f0b2` (TN2a, chưa push); thư mục `22fdx/rx/digital/fpga/`.
> Ký hiệu: ✅ đã kiểm hôm nay (file IP, driver, dữ liệu đã lưu) · ⚠️ ước lượng hoặc giả định · 🔍 kiểm khi làm.
> Bạn duyệt plan này ngày 2026-10-22.

## 0. Context

- **TN2a đã xong** (`cd1f0b2`): TX D-PHY thật của AMD phát vào hai RX. Kết quả: 60/60 run, evidence 10/10, không có lỗi RTL.
  TN2a chỉ phát dữ liệu giả, không có packet CSI-2 và không có controller CSI-2.
- **TN2b theo `PLAN_TN1_TN3.md` §2:** frame RAW10 từ CSI-2 TX SS của AMD, qua pad, vào hai đường nhận CSI-2 đầy đủ:
  - **R-X (mốc):** CSI-2 RX SS 6.0 có PHY, đúng design RX mốc của TN3;
  - **R-F (của mình):** `IBUFDS_DPHY` → `ftel_dphy_rx` (RTL ASIC, không sửa) → CSI-2 RX SS 6.0 không PHY
    (`C_INC_PHY = false`), đúng đường của prototype.
- **Lần đầu PPI của `ftel_dphy_rx` đi vào controller CSI-2 của AMD.** Ba câu hỏi mở của plan prototype chỉ mô phỏng này
  trả lời được:
  - byte clock của mình dừng khi clock lane không ở HS (FP-6);
  - hành vi ở biên PPI khi tắt PHY, AMD chưa có tài liệu (FP-8);
  - miền clock của `stopstate`/`err*` (FP-5). Mô phỏng chỉ trả lời phần chức năng.
- Cấu hình IP chạy được ở đây sẽ ghi vào đặc tả TN3 (`PLAN_TN1_TN3.md` §6: "cấu hình IP ghi trong đặc tả trùng cấu hình
  đã mô phỏng ở TN2").
- **Bạn duyệt cùng plan các điểm sau:**
  - **D4: thư mục mới `exp2b/`.** `exp2.tcl` compile mọi `exp2/*.sv`, và check `sources` của TN2a băm `exp2/*.sv`. Thêm file
    vào `exp2/` sẽ đổi build TN2a và làm check `sources` FAIL trên cả 60 run đã lưu. Đây cũng là lý do `exp2/` ra đời bên
    cạnh `exp1/`.
  - **D5: 4 rate: 260, 800, 1440, 1500 Mb/s.** Ở mức CSI-2, đây là các ca khác nhau:
    - 260: RX mình còn giữ 0–4 byte trailer, nên controller phải bỏ được chúng;
    - 800: rate bring-up của TN3;
    - 1440: rate mục tiêu;
    - 1500: rate cao nhất của R1.

    Mức PHY ở cả 8 rate đã được TN2a phủ.
  - **D6: thêm các kịch bản vận hành mà TN3 sẽ gặp:**
    - E2b-5: đổi số lane lúc chạy;
    - E2b-6: RX bật muộn;
    - E2b-8: tắt rồi bật lại luồng, chỉ báo cáo.
  - **D7: dữ liệu vào là frame tổng hợp do testbench sinh theo công thức** (§2), không phải ảnh mẫu hay frame camera.

## 1. Câu hỏi TN2b trả lời

1. Frame RAW10 do TX SS phát có ra đúng từng pixel ở `video_out` của cả R-X lẫn R-F không? Thanh ghi lỗi của cả ba
   subsystem có sạch không?
2. Controller CSI-2 của AMD có nhận PPI của `ftel_dphy_rx` giống như PPI từ D-PHY của AMD không? Phải cùng chuỗi packet,
   cùng bộ đếm, cùng trạng thái lỗi. Hai trường hợp cần kiểm riêng:
   - byte clock chưa chạy lúc cấu hình RX;
   - byte trailer ở 260 Mb/s.
3. Chuỗi cấu hình theo driver và example của AMD có chạy được khi chưa có byte clock không? TN3 phải theo thứ tự nào?
4. Cấu hình nào của ba subsystem chạy được, để ghi vào TN3?

## 2. Dữ liệu đầu vào và cách so

### 2.1 Dữ liệu vào là gì

Frame **tổng hợp**, do testbench (`axis_vid_gen.sv`) tự sinh theo công thức. Không phải ảnh mẫu, không phải frame lấy từ
camera. Có ba lý do:
1. **Chưa có frame camera nào.** Đường camera trên board dừng ở S0: lần nạp ngày 16/10 làm rớt cổng UART. Tìm trong máy
   thì chỉ có log USB của phiên board và ảnh PGM tổng hợp do selftest của `csi2_dump.py` sinh ra, không có capture nào ✅.
2. **Trong mô phỏng không có camera.**
3. **Với công thức, mỗi pixel mang vị trí của nó** (frame, line, cột). Lệch một pixel, đảo lane, lẫn line, mất hoặc thừa
   line đều lộ ra ngay, kèm vị trí. Ảnh thật có vùng trơn và nhiều pixel kề nhau bằng nhau, nên có thể che các lỗi đó.

**Định dạng:** RAW10 (data type 0x2B), 10 bit mỗi pixel, VC 0, 4 pixel mỗi beat AXI4-Stream.
- Trên dây, TX SS đóng gói 4 pixel thành 5 byte theo CSI-2 v1.3 §11.4.4: 4 byte mang bit [9:2] của từng pixel, byte thứ 5
  gom 2 bit thấp của cả 4 pixel. Cách đóng gói này giống `raw10_pack` của `csi2_dump.py` ✅.
- RX SS mở gói lại thành pixel 10 bit ở `video_out`.

**Ba pattern.** Giá trị pixel p(f, y, x), với f = frame, y = line, x = cột, tính từ 0:

| Pattern | Giá trị pixel | Bắt được gì |
|---|---|---|
| `counter` | p = (x + 37·y + 101·f) mod 1024 | Lệch hoặc đổi chỗ pixel (pixel kề nhau lệch 1), lẫn line (lệch 37), lẫn frame (lệch 101) |
| `prbs` | 10 bit liên tiếp của LFSR x¹⁵ + x¹⁴ + 1, seed = 1 + f·H + y, mỗi line một seed | Lỗi phụ thuộc dữ liệu; ECC/CRC trên payload ngẫu nhiên |
| `synclike` | Dãy lặp 0x2E0, 0x2E0, 0x000, 0x000, 0x3FF, 0x3FF, 0x155, 0x2AA | Payload có byte 0xB8 (giống byte sync), chuỗi 0x00/0xFF dài, 0x55/0xAA |

**Kích thước** theo kịch bản (§6):
- 640 × 16 (WC 800 byte), 3840 × 8 (WC 4800), 64 × 4 (WC 80);
- 2–8 frame mỗi run.

Riêng probe S0 dùng example của AMD với pattern V-TPG của chính nó (YUV422). Checker của example đó chỉ đọc thanh ghi,
không so pixel. Probe này chỉ chứng minh AMD tự chạy được và cho chuỗi thanh ghi của AMD; nó không thuộc phép so ở dưới.

### 2.2 Golden: giá trị mong đợi lấy từ đâu

Ba bản phải trùng nhau trước, rồi mới so đầu ra của hai RX với chúng:
1. **Công thức:** viết lại độc lập trong `tn2b_evidence.py` bằng Python, không dùng code của TB;
2. **`frames.txt`:** những pixel generator đã đưa ra, do TB ghi;
3. **`tx_axis.csv`:** những pixel TX SS thực sự nhận ở cổng AXI4-Stream (beat có `tvalid` và `tready`).

### 2.3 So cái gì với cái gì

| Điểm đo | Dạng dữ liệu | So với | Công cụ |
|---|---|---|---|
| `video_out` của R-X và R-F (`xil_axis.csv`, `ftel_axis.csv`) | pixel 10 bit, theo line, có SOF | golden (§2.2) | `csi2_dump.py compare axis`; decode riêng của `tn2b_evidence.py` |
| PPI của R-X và R-F (`xil_ppi.csv`, `ftel_ppi.csv`) | byte từng lane, ghép thành packet CSI-2 (header, ECC, payload RAW10 đã đóng gói, CRC) | nhau: R-X với R-F; payload sau khi mở gói so với golden | `csi2_dump.py ppi` (ECC, CRC, ảnh theo line), `compare ppi`; decode riêng |
| PPI bên trong TX SS (`tx_ppi.csv`, tuỳ chọn 🔍) | packet controller TX đưa cho PHY của nó | PPI của hai RX | `compare ppi` |
| Thanh ghi (`TB REG`) | bộ đếm packet, cờ lỗi, image info (số line, WC) | R-F với R-X; image info với kích thước frame | `tbcheck` |

**Chuẩn khớp:**
- từng pixel phải bằng nhau tuyệt đối, không có sai số cho phép;
- đúng số line, đúng một SOF mỗi frame, đúng thứ tự frame.

**Không thuộc TN2b:** chạy lại một frame camera thật, hoặc một ảnh mẫu, qua bench. Có thể thêm sau bằng `+IMAGE=<file>`:
generator lấy pixel từ file PGM 16 bit mà `csi2_dump.py --pgm` ghi từ capture ILA của board, và golden là chính file
đó. Chỉ làm khi có frame camera, hoặc khi bạn muốn dùng một ảnh mẫu cụ thể.

## 3. Dữ kiện đã kiểm hôm nay ✅

**CSI-2 TX SS 2.2** (`component.xml`, xgui, changelog trong `mipi_csi2_tx_subsystem_v2_2`):
- **Tham số:**
  - `C_CSI_LANES` 1–4; `C_CSI_PIXEL_MODE` 1/2/4; `C_CSI_MAX_BPC` 8–20;
  - `C_CSI_DATATYPE`: RAW8–RAW14, RGB888/565, YUV422 8 bit, Generic, UserByte; tham số này ẩn trong GUI;
  - `C_CSI_VID_INTERFACE` AXI4S hoặc Native; `C_HS_LINE_RATE`;
  - `C_INC_PHY` (có từ 2024.2, mặc định true); `SupportLevel`; `DPHY_LPX_PERIOD` 50 ns;
  - `C_CSI_CRC_ENABLE`, `C_CSI_EN_ACTIVELANES`, `C_EN_REG_BASED_FE_GEN`: mặc định false;
  - deskew mặc định tắt.

  Không có tham số `C_INIT` cho D-PHY bên trong ⚠️.
- **Controller TX** (`mipi_csi2_tx_ctrl` 1.0):
  - vào: `s_axis_tdata/tkeep/tlast/tvalid/tready`, `tdest[1:0]`, `tuser[95:0]`;
  - ra: PPI của từng lane, `cl_txrequesths`, `dphy_init_done`, `interrupt`.

  Nghĩa của từng bit `tuser` không có trong file IP hay driver. PG260 trên web đòi đăng nhập (HTTP 401) 🔍.
- **Example design của IP:** mô phỏng TX→RX loopback, với cấu hình `1Lane_RGB888_1Pixel_Mode` hoặc
  `4Lane_YUV422_8bit_4Pixel_Mode`.
  - Một ATG ghi thanh ghi của hai subsystem.
  - V-TPG phát một frame.
  - ATG thứ hai đọc ISR, data type và bộ đếm packet của RX để báo PASS/FAIL.

  Template đã mã hoá, phải sinh ra mới đọc được 🔍.

**Thanh ghi và driver** (embeddedsw 2025.2: `csi2tx_v1_5`, `csi2txss_v1_8`, `csi_v1_8`, `mipicsiss_v1_14`):
- **TX:**
  - `CCR` 0x00: bit 0 enable, bit 1 soft reset, bit 2 core ready, bit 4 clock mode (0 = continuous, 1 = non-continuous);
  - `PCR` 0x04: active lanes, max lanes, pixel mode, line generation;
  - `GIER` 0x20, `IER` 0x28, line count VC0–3 0x40–0x4C;
  - `ISR` 0x24: underrun pixel, wrong data type, line buffer full, ULPS, GSP FIFO full, wrong lane config.
- **Driver TX:**
  - `Configure`: soft reset (set, chờ `CCR[2]`, xoá) → active lanes → khôi phục `IER`/`GIER`;
  - `Activate`: `GIER` rồi enable.
- **RX:**
  - `CCR` 0x00: bit 0 enable, bit 1 soft reset;
  - `CSR` 0x10: packet count ở [31:16]; bit 0 = đang reset hoặc core đang tắt;
  - `ISR` 0x24, bit 31 = frame received; các nhóm lỗi của driver:
    - protocol: frame sync/level VC0–3, VCX;
    - packet: ECC 1 bit, ECC 2 bit, CRC, DT lạ;
    - D-PHY: SoT, SoT sync;
    - khác: WC, lane config, line buffer full, stop state;
  - lane info 0x40–0x4C, image info VC0 0x60/0x64.
- **Driver RX:**
  - `Configure`: soft reset → chờ `CSR[0]` → active lanes → xoá soft reset;
  - `Activate`: `GIER` rồi enable.

  Driver không xem vòng chờ có hết giờ hay không.
- **Example camera của AMD** (`xmipi_vek280_example/mipi_cfg.c`: `EnableCSI`, `start_csi_cap_pipe`): CSI-2 RX được bật
  (Reset, Configure, Activate) rồi mới setup và start sensor. Nghĩa là RX được cấu hình khi **chưa có byte clock**.

**`csi2_dump.py`:**
- `compare_seq` không coi hai bên khác độ dài là lỗi. Nó chỉ in "A has …, B has …".
- Một ECC được sửa không tính là lỗi; nó chỉ được đếm vào "ECC corrected".

**CSI-2 RX SS 6.0:**
- **Không PHY** (probe `csi2_rx_no_phy`, 21/10):
  - interface `mipi_ppi_if`; `rxbyteclkhs_in` đi vào `dl0..3_rxbyteclkhs`;
  - `dphy_clk_200M` chính là `core_clk` của controller;
  - `dlN_enable` = shutdown với `CSI_INV_SHUTDOWN = 1`, tức là High = enable;
  - `video_out` 40 bit (RAW10 × 4 pixel); địa chỉ AXI4-Lite 8 bit.
- **Build mốc của board** (repo riêng của nhóm):
  - 4 lane, 1440 Mb/s, RAW10, 4 pixel/clock;
  - `CSI_BUF_DEPTH` 16384, Active Lanes, lọc user data type;
  - `VFB_TU_WIDTH` 96: `tuser` mang SOF, packet error, frame/line number, WC, DT, ECC, CRC;
  - HS settle 141 ns, `SupportLevel` 1;
  - `C_EN_RXPPI_AS_MON`: xuất 48 chân PPI để theo dõi (probe 15/10);
  - `video_aclk` 250 MHz, `lite_aclk` 50 MHz.

**Bench TN2a** (`exp2/README.md` §9):
- Build mất 3 phút cho Vivado và 4 phút compile.
- Mỗi run từ TX mất 85–130 s ở 4 lane, vì TX khởi động 380–571 µs mô phỏng.

**Máy:** 61 GB RAM (28 GB trống lúc kiểm), 24 core, 205 GB đĩa trống.

## 4. Thiết kế bench (`fpga/exp2b/`)

### 4.1 Sơ đồ

```
axis_vid_gen (TB: frame tổng hợp RAW10, 4 pixel/clock, §2 → frames.txt)
  │ AXI4-Stream video (tx_axis.csv)
  ▼
xtxss: CSI-2 TX SS 2.2 (D-PHY MASTER bên trong, continuous clock) ──► pad, hai bản, cùng strong
     ┌─────────────────────────────┬────────────────────────────────────────┬──────────────────┐
     ▼                             ▼                                        ▼                  │
xrxss (R-X): RX SS có PHY      IBUFDS_DPHY → ftel_dphy_rx (RTL ASIC)      afe_model            │
cổng theo dõi PPI → xil_ppi.csv     │ PPI → ftel_ppi.csv                  (line state, term_en)│
     │                              ▼                                                          │
     │                        xrxss_np (R-F): RX SS không PHY                                  │
     ▼ video_out → xil_axis.csv     ▼ video_out → ftel_axis.csv                                │
     └──── so từng pixel với golden (§2.2); thanh ghi của 3 subsystem qua AXI4-Lite ───────────┘
```

### 4.2 Cấu hình IP (`exp2b.tcl`, một build cho mỗi rate)

| IP | Module | Cấu hình |
|---|---|---|
| CSI-2 TX SS 2.2 | `xtxss` | 4 lane, RAW10, 4 pixel/clock, AXI4S, `C_HS_LINE_RATE` = rate, `C_INC_PHY` true, `SupportLevel` 1, Active Lanes, CRC 🔍. Còn lại mặc định |
| CSI-2 RX SS 6.0 có PHY | `xrxss` (R-X) | Như build mốc ở §3, thêm `C_EN_RXPPI_AS_MON`; `DPY_LINE_RATE` = `C_HS_LINE_RATE` = rate; HS settle lấy mặc định của IP theo rate, in ra log |
| CSI-2 RX SS 6.0 không PHY | `xrxss_np` (R-F) | Như R-X, nhưng `C_INC_PHY` false |

`exp2b.tcl` in một dòng `EXP2B` cho mỗi IP, gồm tham số và port. Tham số của D-PHY bên trong TX SS đọc từ file `.bd` do
Vivado sinh ra, bằng `tools/bd_summary.py`.

### 4.3 Nối R-F

Viết lại từ plan prototype, không nêu tên vendor:

| `m_ftel_dphy_rx_wrap` | Hướng | RX SS không PHY | Ghi chú |
|---|---|---|---|
| `o_dphy_rx_rxbyteclkhs` | → | `rxbyteclkhs_in` | một byte clock cho mọi lane |
| `i_dphy_rx_core_clk` | ← | cùng nguồn với `dphy_clk_200M` | `core_clk` 200 MHz |
| `i_dphy_rx_cl_enable`, `i_dphy_rx_dl_enable[x]` | ← | `cl_enable`, `dlx_enable` | TN1 buộc chúng bằng 1; ở đây controller lái (FP-8) |
| `o_dphy_rx_rxdatahs[x]`, `rxvalidhs`, `rxactivehs`, `rxsynchs` | → | `dlx_*` cùng tên | miền `rxbyteclkhs` |
| `o_dphy_rx_cl_stopstate`, `cl_ulpsclknot` | → | `cl_stopstate`, `cl_rxulpsclknot` | |
| `o_dphy_rx_stopstate`, `rxulpsesc`, `errsoths`, `errsotsynchs`, `erresc`, `errcontrol` [x] | → | `dlx_*` cùng tên | phía mình không đồng bộ với `rxbyteclkhs` (FP-5) |
| `i_dphy_rx_forcerxmode[x]` | — | không có | buộc 0 |
| các ngõ ra còn lại | → | không dùng | để hở như TN1 |

Instance wrap vì vậy khác TN1 đúng ở các dòng của bảng này. Check `copy` (§7) liệt kê các dòng được phép khác đó.

### 4.4 Khối mới

**`axis_vid_gen.sv`:**
- Sinh frame theo §2.1: `+FRAMES`, `+WIDTH`, `+HEIGHT`, `+PATTERN=counter|prbs|synclike`. `+LINE_GAP` và
  `+FRAME_GAP` tính bằng clock.
- 4 pixel mỗi beat; tôn trọng `tready`.
- `tuser[0]` = SOF, `tlast` = cuối line. Các trường `tuser` khác theo PG260 và example (🔍 S0).
- Ghi `frames.txt`: mỗi frame một dòng kích thước, mỗi line một dòng pixel hex.

**`axis_csv_mon.sv`:**
- CSV dạng ILA, như `ppi_csv_mon`. Một dòng cho mỗi clock có `tvalid`.
- Cột: `sim_time_ps`, `tdata` (4 × 10 bit), `tvalid`, `tready`, `sof`, `tlast`, `tdest`.
- Ở RX thêm các trường `tuser` 96 bit: packet error, frame/line number, WC, DT.
- `csi2_dump.py axis` đọc được file này với `--tuser sof`.

**`axil_bfm.sv`:**
- AXI4-Lite master với các task `wr`, `rd`, `poll`, có giới hạn thời gian, và kiểm `resp`.
- Mỗi lần truy cập in một dòng `TB AXIL <bus> W|R <addr> <data>`.
- Ba instance: TX, R-X, R-F.

**`tb_exp2b.sv`:**
- **Copy từ `tb_exp1.sv`:**
  - front end của RX mình (`IBUFDS_DPHY` và mux `+AFE`), nguyên văn;
  - front check, chỉ khác dòng đường dẫn: nay so với buffer LP của D-PHY bên trong R-X (đường dẫn 🔍 S0);
  - instance wrap, khác TN1 ở các dòng của §4.3.
- **Phần mới:**
  - clock (§4.5) và pad: hai bản strong, cộng `+NEG_FRONT` theo `in_hs` của `afe_model`;
  - ba subsystem, ba BFM, ba monitor AXIS;
  - hai `ppi_csv_mon`: một trên cổng theo dõi của R-X, một trên PPI vào R-F;
  - `+PPI_CORRUPT=<lane>,<packet>,<byte>,<bit>` (chỉ cho phép thử âm): lật một bit trên PPI của R-F, trước monitor.
- **Tuỳ chọn (🔍 S0):** nếu thấy được PPI bên trong TX SS, ghi thêm `tx_ppi.csv`.
- **Dòng kết quả:**
  - `TB DONE`, `TB FRONT END CHECK`, `AFE`, `TB FTEL CFG`: như TN1;
  - mới: `TB REG <ss> <reg> = <value>`, `TB AXIS <out>` (frame, line, SOF, line có packet error), `TB TX` (số frame,
    ISR).

**`run_exp2b.sh`** (theo `run_exp2.sh`):
- **Lệnh:** `build`, `run`, `E2b-1` … `E2b-8`, `model` (bộ `M_*`), `neg`, `summary`, `recheck`, `evidence`.
- **Build:** hash nguồn gồm RTL, `exp1/{afe_model,ppi_csv_mon}.sv` và `exp2b/*.sv`.
- **Mỗi run ghi `check.txt`** với các lệnh `csi2_dump.py` của §2.3. Script tự đòi hai bên có cùng số line, vì
  `compare_seq` không tự kiểm điều này.
- **Mỗi run ghi `tbcheck.txt`** bằng `tn2b_evidence.py tbcheck`.
- **Kết luận:** run chỉ PASS khi cả hai file đều PASS.

**`tn2b_evidence.py`:** có `tbcheck`, `evidence`, `evselftest`; danh sách check ở §7.

**`probe/csi2_tx_exdes_sim.tcl`:**
- Sinh example TX→RX của AMD (`4Lane_YUV422_8bit_4Pixel_Mode`) trên part của board, rồi chạy nguyên như AMD giao.
- In ra: kết quả của checker trong example, danh sách lệnh ATG (chuỗi thanh ghi của AMD), cách nối `tuser` từ V-TPG vào
  TX SS, thời gian mô phỏng.
- `run_probe.sh`: thêm tên này vào danh sách probe nặng.

### 4.5 Clock, reset, trình tự

| Clock | Tần số | Dùng cho |
|---|---|---|
| `core_clk` (`+CORE_HALF`) | 200 MHz | `dphy_clk_200M` của R-X và R-F, `core_clk` của RX mình |
| `tx_core_clk` (`+TX_CORE_HALF`) | 200 MHz | `dphy_clk_200M` của TX SS |
| `video_aclk` | 250 MHz | `video_out` của hai RX; `s_axis` của TX |
| `lite_aclk` | 50 MHz | ba bus AXI4-Lite (≤ `video_aclk`, như PG232 yêu cầu) |

**Trình tự mặc định**, "RX trước" như example camera của AMD:
1. reset;
2. chờ các D-PHY khởi động;
3. cấu hình rồi bật R-X và R-F theo driver RX, với mọi vòng chờ được ghi log;
4. cấu hình TX theo driver TX, đặt `CCR[4] = 0` (continuous) và đọc lại, rồi bật;
5. chờ clock lane vào HS;
6. phát frame;
7. chờ đủ line ở cả hai `video_out`;
8. đọc thanh ghi;
9. in kết quả.

`+RX_LATE=1` bật hai RX cùng lúc, sau khi TX đã phát. `+STREAM_TOGGLE=1` tắt rồi bật lại TX giữa hai frame.
`+LANES_ACTIVE=<n>` đặt active lanes ở cả ba subsystem.

### 4.6 Dùng lại, không sửa

- `exp1/`: `afe_model.sv`, `ppi_csv_mon.sv`, `cfg_for_rate.py`.
- `tools/csi2_dump.py`: các mode `ppi`, `axis`, `compare` và selftest. `tools/bd_summary.py`.
- Hàm `code_lines`/`block` của `exp2/tn2a_evidence.py`, dùng bằng import.
- `logical/`, `config/`, `exp1/*`, `exp2/*`, `tools/*`: không sửa.
  - Nếu `csi2_dump.py` cần đổi: dừng, đề xuất riêng, rồi `recheck` lại TN1 và TN2a.
  - Nếu TN2b lộ lỗi RTL: dừng và báo kèm bằng chứng. Sửa RTL cần plan riêng.

## 5. Tiêu chí đạt (mỗi kịch bản)

- **R-X phải PASS trước.** Nếu R-X FAIL thì lỗi nằm ở bench, chưa xét R-F.
- **Golden:** công thức, `frames.txt` và `tx_axis.csv` phải trùng nhau (§2.2).
- **Pixel:**
  - `compare axis` của cả hai `video_out` với golden: mọi line trùng nhau, kể từ SOF đầu tiên, và hai bên có cùng số line;
  - decode riêng: mỗi frame có đúng một SOF, H line × W pixel, packet error = 0 ở mọi line.
- **Packet:**
  - `csi2_dump.py ppi` trên cả hai PPI: 0 lỗi ECC/CRC;
  - `compare ppi`: R-X và R-F có cùng chuỗi packet (VC, DT, WC, payload) kể từ FS đầu tiên, cùng số packet;
  - payload sau khi mở gói phải trùng golden.
- **Thanh ghi**, đọc ở cuối run:
  - R-X và R-F: không có bit lỗi nào thuộc các nhóm protocol, packet, D-PHY, WC, lane config, line buffer full; frame
    received = 1;
  - R-F: packet count và image info VC0 bằng của R-X; image info khớp kích thước frame;
  - các bit còn lại (stop state, short packet FIFO) và lane info: so giữa hai RX và báo cáo;
  - TX: ISR = 0.

  Lỗi header 1 bit chỉ hiện ở thanh ghi ECC của controller, vì `csi2_dump.py` coi ECC được sửa là không lỗi. Check thanh
  ghi là nơi bắt lỗi này (NEG-ecc).
- **TB:**
  - `TB DONE OK`;
  - front check: 0 khác biệt trên hơn 0 lần so;
  - `AFE`: 0 lỗi line state; `term_en` không trễ, không thiếu.
- **Chỉ báo cáo:**
  - byte trailer mỗi packet ở PPI của hai RX;
  - khoảng cách giữa các packet do controller TX chọn;
  - độ trễ.

## 6. Kịch bản

| ID | Rate, lane | Dữ liệu và tham số | Mục đích |
|---|---|---|---|
| E2b-1 | 1440, 4 | 2 frame 640×16, `counter` | Cơ bản. R-X phải PASS trước |
| E2b-2a | 1440, 4 | 2 frame 640×16, `prbs` | Payload ngẫu nhiên |
| E2b-2b | 1440, 4 | 2 frame 640×16, `synclike` | Payload có byte giống sync, chuỗi 0x00/0xFF |
| E2b-2c | 1440, 4 | 2 frame 3840×8, `counter` (WC 4800) | Line dài cỡ sensor 4K, khoảng 1200 byte mỗi lane |
| E2b-3 | 1440, 4 | 8 frame 64×4, `counter`, không khoảng nghỉ | FS/FE dày đặc, packet sát nhau |
| E2b-4a/b/c | 260 / 800 / 1500, 4 | như E2b-1 | D5. Ở 260 controller phải bỏ được trailer của mình |
| E2b-5a/b | 1440, 4 (build); 2 / 1 lane active | như E2b-1, `+LANES_ACTIVE` 🔍 | D6: TN3 đổi số lane mà không build lại |
| E2b-6 | 1440, 4 | 4 frame 640×16, `+RX_LATE=1` | D6, FP-6: RX bật giữa frame. Từ FS tiếp theo, cả hai phải ra đúng frame. Frame dở và thanh ghi chỉ báo cáo, vì độ trễ hai PHY khác nhau nên packet đầu tiên mỗi RX thấy có thể khác |
| E2b-7a/b | 1440, 4 | như E2b-3, `+CORE_HALF=2.501` / `2.499` | ±400 ppm giữa TX và hai RX, trên cả đường CSI-2 |
| E2b-8 | 1440, 4 | 4 frame 640×16, `+STREAM_TOGGLE=1` | D6: tắt rồi bật luồng. Chỉ báo cáo, vì HAS R1 cần continuous clock 🔍 |
| M_* | như trên, trừ E2b-8 | `+AFE=model` | RX mình đứng sau `afe_model` |
| NEG-ecc | 1440, 4 | như E2b-1, `+PPI_CORRUPT`: một bit header | R-F phải báo ECC 1 bit; run chỉ FAIL ở mục thanh ghi |
| NEG-crc | 1440, 4 | như E2b-1, `+PPI_CORRUPT`: một bit payload | Phải báo CRC, một pixel sai, packet error; FAIL đúng các mục đó |
| NEG-front | 1440, 4 | như E2b-1, `+NEG_FRONT=1` | Front check (đường dẫn mới) phải đếm ra khác biệt |

**Khối lượng:** 14 kịch bản, 13 run `M_*`, 3 phép thử âm: tổng 30 run. 4 build (260, 800, 1440, 1500), cộng một build
1440 có debug để ghi VCD.

## 7. Kiểm chứng: vì sao sẽ tin được kết quả

| Lớp | TN2b |
|---|---|
| 1. Tín hiệu vào có đúng không | Golden có ba bản phải trùng nhau (§2.2). TX SS là IP của AMD. R-X (PHY và controller đều của AMD) phải ra đúng golden. Example của AMD PASS theo checker của chính nó (S0). Có thể so thêm với packet của controller TX (`tx_ppi.csv`, 🔍) |
| 2. Bộ kiểm có biết báo FAIL không | Selftest của `csi2_dump.py`; NEG-ecc, NEG-crc, NEG-front; `evselftest` cài lỗi vào bản sao của run đã lưu: một pixel, một line thiếu, một thanh ghi, hash, một dòng code copy |
| 3. PASS có tính đúng không | `tn2b_evidence.py decode`: tự giải mã CSV AXIS và PPI (mở gói RAW10), so với công thức; kết quả phải trùng `check.txt` |
| 4. Thứ được test là thứ trong repo | Check `sources` (hash từng run). Check `copy`: front end trùng nguyên văn; front check và instance wrap chỉ khác đúng các dòng đã liệt kê |
| 5. Kết quả đạt không nhờ may | 4 rate; ±400 ppm; line dài; nhiều frame; ba pattern |
| 6. Cùng front end | Front check của mọi run, so với buffer của R-X; NEG-front |
| 7. Controller thấy hai PHY như nhau | Chuỗi packet và thanh ghi của R-F bằng của R-X, ở mọi run |

Ngoài ra còn các check `runs`, `config` (field run-time của RX mình bằng `cfg_for_rate`, dòng `EXP2B` khớp §4.2),
`neg`. Cuối cùng chạy `run_exp2b.sh recheck`: kiểm lại mọi output bằng công cụ hiện tại, không mô phỏng lại.

## 8. Các bước, cổng dừng, ước lượng ⚠️

| Bước | Việc | Cổng: nếu sai thì dừng và báo bạn | Ước lượng |
|---|---|---|---|
| 1 | Lưu `fpga/PLAN_TN2B.md`; thêm ghi chú ngày vào đầu `PLAN_TN1_TN3.md` | — | 0,1 ngày |
| 2 = S0 | Probe `csi2_tx_exdes_sim`; `exp2b.tcl` bản đầu: sinh 3 IP ở 1440 × 4, in tham số và port | (a) example của AMD PASS trên part của board. Nếu không, ghi lý do và dùng driver cộng metadata; (b) có định dạng `tuser` và chuỗi thanh ghi; (c) D-PHY trong TX SS là `mipi_dphy` 4.3 MASTER; ghi lại `C_INIT`, LPX, continuous clock mặc định; (d) có đường dẫn tới buffer LP của R-X; (e) cổng theo dõi PPI đủ chân; (f) đo thời gian sinh IP và compile | 0,5 ngày |
| 3 = S1 | `axil_bfm`, `axis_vid_gen`, `axis_csv_mon`, `tb_exp2b`, `run_exp2b` (build, run, check); E2b-1 | Golden ba bản trùng nhau; R-X PASS trước. Nếu chỉ R-F hỏng mà front check sạch: soát lại bảng nối §4.3, rồi dừng và báo kèm bằng chứng (phát hiện RTL hoặc lệch hợp đồng PPI) | 1 ngày |
| 4 = S2 | E2b-2…8; build 260, 800, 1500; bộ `M_*`; NEG-* | Như trên. Mỗi NEG phải FAIL đúng chỗ đã cài | 0,75 ngày |
| 5 = S3 | `tn2b_evidence.py` (`evidence`, `evselftest`); `recheck` | Evidence PASS mọi check; `evselftest` bắt đủ lỗi đã cài | 0,5 ngày |
| 6 = S4 | `exp2b/README.md`; `fpga/README.md` (trạng thái, cây thư mục, lệnh); phần Kết quả của `PLAN_TN2B.md`; memory | — | 0,25 ngày |

- **Tổng:** khoảng 3,1 ngày ⚠️, trong khoảng 3–4 ngày của plan gốc.
- **Thời gian máy:**
  - mỗi build khoảng 10–15 phút ⚠️, vì có 3 subsystem, và TX SS 2025.2 có SmartConnect bên trong;
  - mỗi run khoảng 2–4 phút ⚠️; 30 run chạy 3 luồng mất khoảng 40 phút;
  - example của AMD khoảng 10–20 phút ⚠️.
- **Bước dài:** báo trước thời gian rồi chạy nền. Trước mỗi pha chạy song song, kiểm RAM trống: dưới 15 GB thì chỉ chạy 2
  luồng.

## 9. File

| File | Việc |
|---|---|
| `fpga/PLAN_TN2B.md` | Mới: bản plan này |
| `fpga/exp2b/`: `exp2b.tcl`, `tb_exp2b.sv`, `axil_bfm.sv`, `axis_vid_gen.sv`, `axis_csv_mon.sv`, `run_exp2b.sh`, `tn2b_evidence.py` | Mới, header FTEL như `exp2/` |
| `fpga/exp2b/README.md` | Mới: ghi chép kỹ thuật nội bộ, tiếng Việt. Có mục dữ liệu vào, golden và cách so, như §2 |
| `fpga/probe/csi2_tx_exdes_sim.tcl` | Mới. `run_probe.sh`: thêm một tên vào danh sách probe nặng |
| `fpga/README.md` | Sửa: trạng thái, cây thư mục, lệnh |
| `fpga/PLAN_TN1_TN3.md` | Sửa: chỉ thêm ghi chú ngày |
| `fpga/work/exp2b/`, `fpga/work/csi2_tx_exdes_sim/` | Output (git bỏ qua) |

**Repo public:**
- chỉ nêu AMD/Xilinx;
- build mốc của board chỉ được nhắc, không nêu tên;
- trước khi commit, quét danh sách token trên các file mới;
- commit chỉ khi bạn bảo.

## 10. Rủi ro

1. **Example của AMD không sinh hoặc không chạy được trên xcvp1902** (ATG, V-TPG): dùng driver, PG và metadata IP. Ghi rõ
   ở README.
2. **D-PHY trong TX SS không cho đặt `C_INIT`**, có thể là 1 ms, nên mỗi run dài hơn. Cách giảm: chạy song song.
3. **Chưa biết `tuser` của TX SS:** cổng S0. Nếu vẫn không rõ, đọc netlist do Vivado sinh ra và thử bằng R-X.
4. **Không truy cập được buffer LP bên trong R-X:** thêm `xrx` trần của TN1, chỉ để làm front check với code nguyên văn.
   Cái giá là thêm một model D-PHY RX.
5. **Vòng chờ reset của RX treo khi chưa có byte clock** (FP-6):
   - nếu cả R-X lẫn R-F cùng treo: ghi lại thành thứ tự bắt buộc cho TN3;
   - nếu chỉ R-F treo: đó là phát hiện, dừng và báo.
6. **Active lanes lúc chạy không chạy được với D-PHY trong TX SS:** bỏ E2b-5 hoặc thêm hai build (2 lane, 1 lane), và báo
   bạn.
7. **R-F hỏng, R-X đạt, front check sạch:** soát bảng nối trước. Nếu vẫn hỏng thì đó là phát hiện RTL hoặc lệch hợp đồng
   PPI: dừng, báo, sửa theo plan riêng.
8. **Phát hiện chạm tới hợp đồng PPI với team CSI:** chỉ báo cho bạn kèm ảnh hưởng, không tự quyết thay team khác.
9. **Mô phỏng nặng** (3 subsystem): đo ở S0. Nếu nặng quá thì giảm kích thước frame, không giảm số kịch bản.

## 11. TN2b không kiểm

- **Frame camera thật và ảnh mẫu:** chưa có, xem §2.3.
- **CDC và metastability** của các ngõ ra PPI không đồng bộ của RX mình (FP-5): mô phỏng không có metastability. Phần này
  thuộc TN2c và TN3 (`report_cdc` của build FPGA).
- Bản FPGA của RX mình (TN2c).
- Non-continuous clock, ULPS, escape, deskew, nhiều VC, data type khác RAW10, embedded data.
- Hiệu ứng board, analog và skew (TN1 đã phủ ±0,2 UI).
- 400, 600, 1000, 1200 Mb/s ở mức CSI-2. Mức PHY ở các rate này đã có trong TN2a.

## 12. Sau TN2b (chưa thuộc plan này)

- **Bàn giao TN2** (D3): `TN2_DESCRIPTION.md` và `TN2_REPORT.md`, phủ cả 2a và 2b.
- **TN3:**
  - lấy cấu hình IP đã mô phỏng (dòng `EXP2B`) cho §5–6 của đặc tả;
  - dùng thứ tự cấu hình tìm được ở E2b-1 và E2b-6;
  - khi board bắt được frame camera, có thể chạy lại frame đó qua bench (`+IMAGE`, §2.3).
- **TN2c:** để sau.
- **Còn chờ bạn:**
  - push `cd1f0b2`;
  - commit thay đổi 29/09 của portable-memory;
  - các hash DPHY được dẫn trong tài liệu fu3;
  - lệnh `/dphy_*`;
  - plan prototype v0.6.

## 13. Độ tin cậy

- **HIGH:**
  - thanh ghi và chuỗi driver (đọc mã nguồn driver hôm nay);
  - tham số và port của RX SS (probe 21/10 và `component.xml`);
  - tham số của TX SS;
  - cách đóng gói RAW10 và cách so (§2);
  - phần dùng lại của TN1 và TN2a.
- **MED:**
  - định dạng `tuser`;
  - example của AMD chạy được trên part của board;
  - thời gian build và run;
  - active lanes lúc chạy;
  - hành vi FP-6.
- **Kỳ vọng kết quả:** MED-HIGH là R-F đạt. Mức PHY giống TN2a, vì D-PHY TX là cùng IP (S0 xác nhận). Rủi ro mới nằm ở hợp
  đồng PPI với controller của AMD (FP-5, FP-8) và ở byte clock dừng (FP-6).

## 14. Phát hiện khi làm (2026-10-22/23)

1. **S0 đạt.** Example TX→RX của AMD (`4Lane_YUV422_8bit_4Pixel_Mode`) sinh và chạy được trên part của board:
   checker của example báo "Test completed successfully" ở 608,8 µs mô phỏng (`probe/csi2_tx_exdes_sim.tcl`).
   `tuser` của TX lấy theo example: [0] SOF, [32:1] data type, [63:48] word count. Example bật TX bằng `CCR` = 1 rồi
   chờ `CCR[2]`.
2. **TX SS chỉ xin HS clock khi có video:** `cl_txrequesths` lên 180 ns sau beat đầu (1440 Mb/s). Khi chưa có video,
   clock lane ở LP mãi. E2b-1 đầu tiên chờ clock lane rồi mới phát video, nên kẹt tới 3,4 ms (giữ ở
   `work/exp2b/aborted/`). Bench nay phát video ngay sau core ready, như example; dòng `TB TX` ghi lúc controller xin HS
   và lúc mỗi RX thấy.
3. **Phát hiện (FP-8): controller CSI-2 không PHY của AMD không nhận PPI của `ftel_dphy_rx`.** Chi tiết ở
   [`exp2b/README.md`](exp2b/README.md) §6.1.
   - R-X đạt từng pixel. PPI vào R-F mang đúng chuỗi packet của R-X, nhưng R-F ra 0 line, đếm 0 packet, ISR không cờ
     lỗi nào.
   - Đầu burst: `ftel_dphy_rx` nâng `rxactivehs` trước `rxsynchs` (7 byte clock ở 260 Mb/s, 12 ở 800, 19–20 ở 1440
     và 1500),
     `rxsynchs` cùng byte đầu (HAS C6, dòng 909 "rises at or before"). D-PHY của AMD nâng hai tín hiệu cùng lúc, byte
     đầu ở cycle sau.
   - Chẩn đoán bằng shim trong TB (`+PPI_AMD_TIMING`): mode 1 (như D-PHY AMD) và mode 3 (chỉ giữ `rxactivehs` tới
     `rxsynchs`) đạt; mode 2 (chỉ dời `rxsynchs`) không. Quy luật: `rxactivehs` không được lên trước `rxsynchs`. Mode 3
     là thay đổi nhỏ nhất: mỗi lane một flop và một cổng, không thêm trễ.
   - Theo HAS thì không phải lỗi RTL. HAS (Bảng A-2) còn ghi yêu cầu C8 của team CSI: sau lỗi sync, `rxactivehs` giữ
     tới EoT dù không có `rxsynchs`; HAS docx của team CSI cũng giữ `rxactivehs` trong burst deskew. Đổi convention
     vì vậy đụng hợp đồng với team CSI.
   - Phương án A (shim chỉ ở FPGA), B (option trong RTL), C (convention chung với team CSI): chờ bạn quyết. Ngày
     23/10 bạn chọn chạy S2 và S3 với shim mode 3 trong TB (run `SH_*`), giữ 9 run không chỉnh làm bằng chứng
     (`run_exp2b.sh finding`).
   - Cũng ngày 23/10, sau ma trận A/B/C, bạn chọn A. Khối FPGA `fpga/rtl/m_ftel_ppi_act_gate.sv` thay shim mode 3
     của TB trong các run `SH_*` (`+PPI_ADAPTER=1`), thêm kịch bản E2b-9 (lỗi sync ở một lane). Plan, kiểm và kết
     quả: [`PLAN_TN2B_GATE.md`](PLAN_TN2B_GATE.md).
4. **Hai giả thuyết đã loại:**
   - X trên `rxdatahs` khi `rxvalidhs` = 0: 32 cycle đầu, do flop dữ liệu của delay line EoT không có reset (theo thiết
     kế, như ở TN1/TN2a). `+PPI_XFILL=1` không đổi gì.
   - Byte clock không có lúc reset (FP-6): chỉ để lại X ở bit 27:24 của ISR R-F (mục 5).
5. **Bit 27:24 của ISR R-F là X** khi R-F được cấu hình lúc chưa có byte clock: 36/39 run, mọi run trừ ba run E2b-6.
   - Driver của AMD không định nghĩa bit 27:23 (`XCSI_ISR_ALLINTR_MASK` = 0xF07FFFFF).
   - R-X không gặp, vì D-PHY của AMD có byte clock ngay khi khởi động.
   - `tbcheck` đọc được chữ số X: X ở bit frame received hay bit lỗi thì FAIL, X ở bit khác chỉ in ra.
6. **`tuser[1]` ở `video_out` luôn 0 với dữ liệu pixel.** RTL của VFB (`vfb_v1_0`) ghép đầu ra thành `{ECC/CRC, 2'b0,
   DT, WC, line, frame, 15'h0, SOF}`. Cờ lỗi từ controller chỉ kết thúc line. Mục "packet error" của §5 và của NEG-crc
   vì vậy không thể báo; bạn chọn bỏ mục này (23/10).
7. **TX SS chỉ gửi FE của một frame khi bắt đầu frame kế** (`C_EN_REG_BASED_FE_GEN` mặc định false; nguyên nhân chưa
   đọc được, RTL TX đã mã hoá). Frame cuối mỗi run không có FE trên cả ba PPI; E2b-8 thiếu thêm FE của frame 0.
8. **RX SS bật ngay sau reset** (`CCR` = 1). Ở E2b-6 hai RX ra một phần frame 0 trước khi được cấu hình, và mỗi RX cắt
   ở một chỗ khác (R-X 63 line, R-F 64). Check vì vậy so từ SOF đầu tiên sau lúc mỗi RX được cấu hình (`TB RX CFG`),
   và TB chờ tới khi hai `video_out` yên 30 µs (`drain_quiet`) thay vì đếm line.
9. **E2b-8 kiểm FP-6 thật:** lúc TX tắt, clock lane rời HS và byte clock của cả hai RX dừng (413,2–797 µs); R-F vẫn ra
   đúng cả 4 frame.
10. **Bench:**
    - hai run XSIM chung một thư mục sim thì run sau chạy với plusarg của run trước, nên mỗi run nay copy thư mục sim
      riêng (37 MB);
    - bộ nhớ `xsimk` tăng khoảng 1,2–1,5 GB mỗi phút chạy; `rss.txt` ghi lại mỗi 10 s.

## 15. Kết quả (2026-10-23)

**39/39 run ra đúng kỳ vọng. `tn2b_evidence.py evidence`: PASS (11/11 checks); `evselftest`: PASS (14 ca).** Chi
tiết và bảng số nằm ở [`exp2b/README.md`](exp2b/README.md) §6–§7. RTL `logical/` và `config/` không đổi so với
`cd1f0b2`; mọi run cùng hash nguồn `1ac03101efd59a1a`.

- **R-X:** PASS từng pixel ở mọi run.
- **R-F với PPI như hiện nay:** 0 line ở cả 4 rate (5 run), dù PPI mang đúng packet của R-X (§14 mục 3, FP-8).
- **R-F khi testbench giữ `rxactivehs` tới `rxsynchs`** (shim mode 3, run `SH_*`): 27/27 run PASS cho cả hai RX.
  - 14 kịch bản: 4 rate, 2 và 1 lane active không build lại, ±400 ppm, RX bật muộn, tắt rồi bật lại luồng; cộng 13
    run sau `afe_model`.
  - Chuỗi packet, packet count, image info và cờ lỗi của R-F bằng R-X ở mọi run được chấm (24 run; E2b-6, `M_E2b-6`
    và E2b-8 chỉ báo cáo).
- **Phép thử âm:**
  - NEG-ecc: header được sửa, chỉ thanh ghi ECC 1 bit của R-F báo;
  - NEG-crc: pixel sai duy nhất của R-F đúng là pixel mà bit cài thuộc về (frame 0, line 0, pixel 4), chỉ R-F báo CRC;
  - NEG-front: 356 598 / 370 519 lần so khác, R-X vẫn đạt.
- **Trả lời bốn câu hỏi của §1:**
  1. R-X có. R-F có khi đầu burst được chỉnh. Thanh ghi sạch: ISR của TX = 0; ISR của R-F chỉ X ở bit dự trữ 27:24
     (§14 mục 5).
  2. Có, khi đầu burst được chỉnh: cùng chuỗi packet, cùng bộ đếm, cùng cờ lỗi. Cấu hình lúc chưa có byte clock chạy
     được. Trailer của RX mình ở 260 Mb/s (0–8 byte sau `afe_model`) và của D-PHY AMD (8–74 byte) đều được controller
     bỏ.
  3. Thứ tự của AMD (RX trước, rồi TX) chạy được; RX cấu hình muộn cũng chạy, từ SOF kế tiếp. Cho TN3: che ISR bằng
     mặt nạ của driver (0xF07FFFFF).
  4. Cấu hình ở `exp2b/README.md` §3: các dòng `EXP2B` của từng build, kiểm bằng check `config`.
- **Số đo** (README §6.5): R-F trễ hơn R-X 172–948 ns tuỳ rate (khoảng 31–32 byte time), bằng độ trễ thêm TN2a đo ở
  PPI; D-PHY AMD giữ 8–74 byte trailer mỗi packet, RX mình 0 sau `IBUFDS_DPHY`.
- **Kiểm chính script kiểm chứng:**
  - `evselftest`: 1 ca sạch và 13 lỗi cài; mỗi lỗi làm hỏng đúng các check của nó;
  - `run_exp2b.sh recheck`: 39 `check.txt` không đổi; 9 `tbcheck.txt` chỉ đổi chữ ở dòng `axis`, kết luận không đổi
    (README §7.1).
- **Thời gian máy:** 4 build compile lại khoảng 16 s; 39 run chạy 3 luồng trong 35 phút (tổng 6 038 s), mỗi run
  121–252 s và 2,4–5,1 GB.

**Khác với plan:**
- **Không chờ clock lane trước khi phát video** (§4.5 bước 5), vì TX chỉ xin HS khi có video (§14 mục 2).
- **S2 và S3 chạy với shim mode 3 trong testbench** (run `SH_*`, `run_exp2b.sh shim`), do bạn chọn sau phát hiện
  FP-8. Thêm 9 run làm bằng chứng của phát hiện (`run_exp2b.sh finding`), và hai plusarg chẩn đoán (`+PPI_XFILL`,
  `+PPI_AMD_TIMING`). Tập chấm vì vậy có 39 run thay vì 30.
- **Bỏ mục packet error ở `video_out`** (§2.3, §5, NEG-crc), do bạn chọn (§14 mục 6).
- **E2b-6:** check so từ SOF đầu tiên sau lúc mỗi RX được cấu hình, và TB chờ hai `video_out` yên 30 µs (§14 mục 8).
- **`tbcheck` đọc được chữ số X** của thanh ghi (§14 mục 5).
- **Bench:** mỗi run copy thư mục sim riêng; `rss.txt` ghi bộ nhớ (§14 mục 10). Run E2b-1 bị kẹt lần đầu được giữ ở
  `work/exp2b/aborted/`, không thuộc tập kiểm.
- **`tn2b_evidence.py` có thêm, ngoài plan:** `selftest` của bộ giải mã; check `finding`; lệnh `report` in các số
  "chỉ báo cáo" của §5.
- `tx_ppi.csv` (tuỳ chọn 🔍 ở §4.4) làm được: PPI bên trong TX SS đọc được qua đường dẫn của block design. Không cần
  build debug: các chẩn đoán dùng capture CSV.
- **Thời gian:**
  - Plan ước 3,1 ngày công; thực tế làm trong ngày 22–23/10.
  - Build nhanh hơn ước rất nhiều: Vivado khoảng 40 s, compile lại khoảng 16 s (plan ước 10–15 phút). Run 121–252 s
    (plan ước 2–4 phút).
