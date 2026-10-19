# Plan: ba thí nghiệm cho D-PHY RX — TN1, TN2 làm trong Vivado; TN3 viết đặc tả cho team FPGA (2026-10-19)

> Repo `/home/linhhk/Documents/DPHY`, branch `dev`, thư mục `fpga/`.
> Ký hiệu: ✅ đã kiểm hôm nay · ⚠️ ước lượng hoặc giả định · 🔍 kiểm khi làm.
>
> **Cập nhật 2026-10-19 (sau khi duyệt):** VEK280 không làm TX được. Lý do: bank 705/706 của FMCP1 nối vào VADJ_FMC cố định 1.5 V (UG1612), trong khi `MIPI_DPHY` cần VCCO 1.2 V. Bạn chọn phương án B: TX đặt trên một board thứ hai có FMC chạy được 1.2 V, chờ team FPGA cho biết họ có board nào. Bằng chứng, yêu cầu và câu hỏi nằm ở `fpga/exp3/TN3_SPEC.md` v0.1 (phần 1). Thư mục `tx_vek280/` ở §4 đổi tên theo board TX khi đã chốt. Probe `fpga/probe/tn3_pins.tcl` được thêm vào.

## 0. Context

**Vì sao đổi hướng.** Đường camera (S0 → S1 → S2) vướng ba chỗ:
- phải ngồi board;
- cổng USB của board hay rớt (log 15–19/10);
- cần camera.

Sếp đã hỏi "thử giả lập data từ TX đẩy vô chưa" (15/10), và giao thí nghiệm VEK280 (TX) → mạch test → VP1902 (RX).

Bạn chia lại thành ba thí nghiệm, theo nguyên tắc: việc nào làm được trong Vivado thì làm trong Vivado; việc thật sự cần FPGA thì viết thí nghiệm chi tiết để team FPGA làm.

**Bạn đã chốt (19/10):**
- **TN1:** so **RTL ASIC** của `ftel_dphy_rx` (mô hình AFE nằm trong testbench) với D-PHY RX của Xilinx.
- **TN2:** chỉ mô phỏng trong Vivado.
- **TN3:**
  - TX trên VEK280 dùng **MIPI CSI-2 TX Subsystem** của Xilinx;
  - mình vẫn build design, nhưng team FPGA nhiều khả năng sẽ build lại, nên **đặc tả phải đủ để họ build lại từ đầu**.

**Dữ kiện đã kiểm hôm nay ✅**
- **IP:** Vivado 2025.2 có sẵn ba IP sau, đều hỗ trợ Versal, không cần license:
  - `mipi_dphy` 4.3 (chạy được cả TX lẫn RX);
  - `mipi_csi2_tx_subsystem` 2.2;
  - `mipi_csi2_rx_subsystem` 6.0.

  Có board file VEK280 (`xcve2802-vsvh1760-2MP-e-S`, bản 1.0–1.2).
- **RTL `ftel_dphy_rx`:** đã có draft đủ các block, lint sạch. Nhưng mới chỉ mô phỏng Block No. 1 (TB B7, VCS). **Chuỗi pads → PPI chưa từng mô phỏng trọn**, nên TN1 cũng là lần mô phỏng end-to-end đầu tiên.
- **Cấu hình R1:**
  - dải 80–1500 Mb/s, 4 lane, `core_clk` 200 MHz, cần continuous clock;
  - `hs_settle_cyc` và `eot_skip_bytes` đổi theo line rate. Model trong `config/validate_config.py` đã có hàm `hs_settle(rate)` và `eot_skip(rate)`.
- **Chân camera trên VP1902** (FMC+ 01, bank 705, netlist sheet FMC01):

  | Lane | Chân FMC | Tên FMC | Ball |
  |---|---|---|---|
  | CLK | H4/H5 | `CLK0_M2C` | CV60/CV59 |
  | D0 | C14/C15 | `LA10` | CY61/DA61 |
  | D1 | G2/G3 | `CLK1_M2C` | CT61/CU61 |
  | D2 | G12/G13 | `LA08` | DC60/DC59 |
  | D3 | C10/C11 | `LA06` | DA60/DA59 |
- **Cùng các chân FMC đó trên VEK280 (FMCP1):** `CLK0_M2C` nằm ở **bank 705**, bốn cặp còn lại ở **bank 706** (theo device DB của Vivado). Nếu mạch test nối thẳng chân trùng tên thì TX trên VEK280 sẽ bị chia sang hai bank.

## 1. TN1 — dummy data vào hai RX (mô phỏng XSIM)

**Câu hỏi cần trả lời:**
- Cùng một tín hiệu D-PHY trên pad, RX của mình và RX của Xilinx có cho cùng dữ liệu ở PPI không?
- Cả hai có nhận đúng những byte đã phát không?

```
TB line generator (dummy data, timing D-PHY chỉnh được) ──► file truth (byte đã phát)
   ├─ pad p/n ─────────────────► mipi_dphy 4.3 RX (SLAVE, 4 lane) ─────────► CSV PPI Xilinx ─┐
   └─ pad p/n ─► mô hình AFE ─► m_ftel_dphy_rx_wrap (RTL ASIC, R1) ─► CSV PPI mình ─────────┴─► so với truth và với nhau
```

**Các khối của testbench:**
- **Line generator (SystemVerilog, testbench):**
  - clock lane vào HS một lần rồi chạy continuous; xung DDR có cạnh nằm giữa bit;
  - mỗi burst trên data lane: LP-11 → LP-01 → LP-00 → HS-0 → sync 0xB8 → payload (LSB trước) → trail → LP-11;
  - TLPX, THS-PREPARE/ZERO/TRAIL/EXIT, TCLK-*, skew giữa lane và pha clock đều chỉnh bằng plusarg. Mặc định đặt giữa khoảng cho phép của D-PHY v1.1;
  - nửa UI làm tròn theo độ phân giải ps (bài học của B7);
  - ghi file truth: lane, burst, byte.
- **Mô hình AFE (SystemVerilog, testbench):**
  - đổi pad thành `afe_lp_dp/dn`, `afe_hs_bit_x`, `afe_cl_hs_clk`;
  - khi line đang ở HS thì LP đọc LP-00, như phần cứng thật. Mô hình suy ra trạng thái HS từ chuỗi LP trên pad: LP-01 → LP-00 → HS, phân biệt với lối vào escape bắt đầu bằng LP-10;
  - có checker kiểm `afe_term_en`/`afe_hs_en` có bật trong cửa sổ TD-TERM-EN không. Checker chỉ báo cáo, không làm FAIL.
- **RX Xilinx:** `mipi_dphy` 4.3, SLAVE, 4 lane, SupportLevel 1, cách tạo theo `fpga/probe/dphy_exdes_sim.tcl`. Line rate là tham số lúc build, nên mỗi rate sinh một IP.
- **RX mình:**
  - RTL ASIC lấy từ `hw/rtl/ip/ftel_dphy_rx/logical/filelist.f`, **không sửa**;
  - field run-time tính theo rate bằng model của `validate_config.py`, chỉ import để dùng.
- **Monitor:**
  - mỗi RX ghi một file CSV đúng format ILA, cột `dl{n}_rxdatahs`, `dl{n}_rxvalidhs`, `dl{n}_rxactivehs`, `dl{n}_rxsynchs`, `dl{n}_errsoths`, `dl{n}_errsotsynchs`, `dl{n}_stopstate`, `cl_stopstate`;
  - nhờ vậy cùng một công cụ đọc được cả mô phỏng lẫn ILA phần cứng ở TN3.
- **So sánh:**
  - thêm mode `bursts` vào `fpga/tools/csi2_dump.py`, dùng lại bộ đọc CSV và cách cắt burst sẵn có;
  - so từng lane, từng burst: byte nhận được (`rxvalidhs` = 1) với truth, và giữa hai RX.

**Kịch bản:**

| ID | Nội dung | Mục đích |
|---|---|---|
| E1-1 | 4 lane, 1440 Mb/s; burst dài 1, 2, 3, 4, 5, 8, 16, 64, 256, 1024 byte; payload là counter theo lane | Cơ bản, ở đúng rate của camera |
| E1-2 | Như E1-1, payload PRBS-9 và payload chứa mẫu giống sync (0xB8, 00011101) | Sync chỉ khoá một lần |
| E1-3 | Góc timing: THS-PREPARE min/max, THS-ZERO min, THS-TRAIL min, THS-EXIT min (burst sát nhau), TLPX min; skew giữa lane và pha clock ở biên cho phép | Biên timing |
| E1-4 | 80, 800, 1500 Mb/s × 4 lane; 1 lane và 2 lane ở 1440 Mb/s | Phủ dải R1 và số lane |
| E1-5 (tuỳ chọn) | ULPS vào/ra trên data lane và clock lane | `stopstate`, `ulpsactivenot` |
| E1-6 (chỉ báo cáo) | Non-continuous clock | HAS R1 cần continuous clock; ghi lại khác biệt |

**Tiêu chí:**
- **Điều kiện trước:** chạy E1-1 với riêng RX Xilinx phải PASS. Việc này chứng minh line generator đúng.
- **E1-1 đến E1-4 PASS** khi cả hai RX nhận đủ, đúng thứ tự, toàn bộ payload đã phát ở phần đầu mỗi burst, và không bật cờ lỗi nào.
- **Khác biệt đã biết**, chỉ báo cáo, không tính là lỗi:
  - độ trễ;
  - số byte trailer ở cuối burst. Theo HAS thì RX mình cắt trailer, còn RX Xilinx có thể để lại;
  - thời điểm `stopstate`/`rxactivehs` (ADR-006).

## 2. TN2 — TX → RX trong cùng một design VP1902 (mô phỏng XSIM)

**2a — dummy data qua TX thật:**
- `mipi_dphy` 4.3 MASTER, continuous clock 🔍 (tên tham số kiểm khi làm).
- Testbench lái PPI TX (`txrequesths`, `txdatahs`); tín hiệu ra pad đi vào hai RX như ở TN1.
- Khác TN1 ở chỗ timing và trailer là của TX Xilinx thật. Tiêu chí như TN1.

**2b — frame RAW, không cần camera:**
```
AXIS frame generator (TB, RAW10, pattern biết trước, frame nhỏ)
  → mipi_csi2_tx_subsystem 2.2 (4 lane, continuous clock) → pad
      ├─► mipi_csi2_rx_subsystem 6.0 có PHY (mốc) ──────────────────────────► AXIS video_out ─┐
      └─► mô hình AFE → RTL mình → mipi_csi2_rx_subsystem 6.0, C_INC_PHY=false ─► AXIS video_out ─┴─► so frame
```
- Testbench có AXI4-Lite BFM để bật hai subsystem. Thanh ghi lấy theo driver Xilinx sinh kèm IP 🔍.
- Nối PPI theo bảng §3.3 của plan FPGA. Ở đây kiểm luôn FP-6: controller CSI-2 xử lý thế nào khi byte clock của mình bị gate.
- **Tiêu chí:**
  - hai `video_out` trùng từng pixel với frame đã phát (`csi2_dump.py compare axis`);
  - thanh ghi lỗi ECC/CRC/SoT của hai CSI-2 RX đều bằng 0.
- Phần RX của 2b (cấu hình CSI-2 RX, ILA) dùng lại làm phía RX của TN3.

**2c — bản FPGA của RX mình** (điều kiện để TN3 chạy được RX mình; đây là bước F3 cũ):
- Block No. 1-F: XPHY của Advanced IO Wizard `MIPI_RX` thay sampler, deserializer và byte clock.
- Biến thể FPGA sinh từ RTL ASIC bằng script, theo plan FPGA §3.1. Script kiểm rằng phần còn lại trùng bản ASIC.
- Chạy lại 2b với biến thể này.
- Pha mốc của TN3 không phụ thuộc bước này.

## 3. TN3 — VEK280 (TX) → mạch test → VP1902 (RX): đặc tả cho team FPGA

**Sản phẩm:**
- `fpga/exp3/TN3_SPEC.md`, tiếng Việt, viết cho team FPGA, đủ để build lại từ đầu. Khi xong thì publish thành Artifact để chia sẻ; bản trong repo là bản gốc.
- Script build và PDI/LTX do mình build.

**Mục lục đặc tả:**
1. **Mục tiêu:** thí nghiệm chứng minh được gì, không chứng minh được gì.
2. **Sơ đồ hệ thống** và luồng tín hiệu.
3. **Phần cứng và cài đặt:**
   - **VEK280:** VADJ của bank TX = 1.2 V (cách đặt lấy theo tài liệu VEK280 🔍); boot mode JTAG.
   - **VP1902:** SW192 = 1.2 V; SW1 = JTAG; FMC+ 01 chỉ cắm mạch test.
   - **Mạch test:**
     - 5 cặp vi sai (CLK, D0–D3), 100 Ω ±10 %;
     - độ lệch trong cặp và giữa các lane tính sẵn từ ngân sách skew của D-PHY ở rate cao nhất;
     - có chiều dài tối đa đề xuất;
     - nhiều chân GND giữa hai đầu, không stub.
   - **Quy tắc vận hành:**
     - thứ tự bật nguồn;
     - không cắm/rút khi đang có điện;
     - không phát HS khi board bên kia chưa có nguồn;
     - bài học USB ngày 16/10: cáp JTAG/UART rớt mỗi khi board đổi trạng thái điện, phải cắm lại.
4. **Bảng chân:**
   - phía VP1902 cố định, theo bảng §0;
   - phía VEK280: đề xuất đặt cả 5 lane TX trong bank 706, để mạch test nối chéo sang chân camera của VP1902. Xác nhận bằng DRC khi build TX 🔍;
   - netlist của mạch test: đầu VEK280 → đầu VP1902.
5. **Design TX (VEK280):**
   - CSI-2 TX SS 2.2, nguồn AXIS (counter, PRBS, frame RAW10), điều khiển bằng VIO hoặc `xsdb`, ILA;
   - liệt kê đủ IP, phiên bản, mọi tham số khác mặc định, clock, reset, XDC.
6. **Design RX (VP1902):**
   - **R-X (mốc):** CSI-2 RX SS có PHY trên chân camera, lấy từ build S0 và bỏ phần điều khiển camera; ILA ở PPI, AXIS, LP;
   - **R-F (của mình):** RX mình bản FPGA (2c) + CSI-2 RX SS không PHY, cùng chân, cùng ILA;
   - điều khiển bằng `xsdb mwr` qua JTAG, **không cần UART**.
7. **Quy trình từng bước:**
   1. kiểm trước khi bật nguồn;
   2. nạp VEK280, để TX tắt;
   3. nạp VP1902 với R-X;
   4. bật RX, rồi bật TX ở rate thấp;
   5. bắt ILA và kiểm;
   6. tăng rate và số lane;
   7. làm lại toàn bộ với R-F.
8. **Tiêu chí đạt mỗi bước:**
   - 0 lỗi ECC/CRC/SoT;
   - số frame nhận bằng số frame phát;
   - dữ liệu ILA trùng pattern (`csi2_dump.py`);
   - giữ được qua N frame liên tiếp.
9. **Dữ liệu gửi về:** quy ước tên file, ảnh, log.
10. **Bảng xử lý sự cố.**
11. **Phụ lục:** tham số IP xuất từ Vivado, XDC, lệnh Tcl.

**Rate:** bring-up ở 800 Mb/s, mục tiêu 1440 Mb/s, tuỳ chọn 1500 Mb/s. Line rate là tham số lúc build, nên mỗi rate cần một bộ build TX và RX riêng.

**Gửi team FPGA trước:** mục 3 và 4 (yêu cầu mạch test, bảng chân), vì làm mạch test là việc tốn thời gian nhất.

## 4. File sẽ tạo/sửa (sau khi duyệt)

| File | Việc |
|---|---|
| `fpga/exp1/`: `tb_exp1.sv`, `dphy_line_gen.sv`, `afe_model.sv`, `exp1.tcl`, `run_exp1.sh` | TN1 |
| `fpga/exp2/`: `tb_exp2a.sv`, `tb_exp2b.sv`, `axil_bfm.sv`, `exp2.tcl`, `run_exp2.sh` | TN2a, TN2b; 2c thêm script sinh biến thể FPGA |
| `fpga/tools/csi2_dump.py` | Mode `bursts` (so với truth) và selftest cho mode này |
| `fpga/exp3/`: `TN3_SPEC.md`, `tx_vek280/*.tcl`, `rx_vp1902/*.tcl`, `xsdb/*.tcl` | TN3 |
| `fpga/FPGA_PROTO_PLAN.md` (lên v0.6), `fpga/README.md` | §6 chuyển sang TN1–TN3; S0 thành build mốc R-X; thêm rủi ro mới |
| Output | `fpga/work/exp*/` (gitignored) |

**Dùng lại, không viết mới:**
- cách tạo IP và mô phỏng của `fpga/probe/dphy_exdes_sim.tcl`, cùng khung `run_probe.sh`;
- bộ đọc CSV và các mode ppi/axis/compare của `fpga/tools/csi2_dump.py`;
- `fpga/tools/f2_timing.py` để đo độ trễ;
- model rate trong `config/validate_config.py`;
- script S0 trong `fpga/build/` (cho R-X) và proc `s0_cap` để bắt ILA.

**Không sửa RTL** trong `hw/rtl/ip/ftel_dphy_rx/`. Nếu TN1/TN2 lộ lỗi RTL thì dừng lại, báo kèm bằng chứng; sửa RTL cần plan riêng.

## 5. Thứ tự và ước lượng ⚠️

| Việc | Ước lượng | Phụ thuộc |
|---|---|---|
| TN3 mục 3–4 (yêu cầu mạch test, bảng chân) | 0,5–1 ngày | không; gửi team FPGA sớm |
| TN1 | 3–5 ngày, chưa tính thời gian sửa lỗi RTL | không |
| TN2a | 1–2 ngày | TN1 |
| TN2b | 3–4 ngày | TN2a |
| TN3: đặc tả đầy đủ + build TX và R-X | 2–3 ngày | TN2b (cấu hình IP đã mô phỏng) |
| TN2c (bản FPGA của RX mình) + build R-F | khoảng 1 tuần | TN2b |

Mỗi bước dài sẽ báo trước thời gian chạy. Build trên VP1902 chạy dưới `ram_watch.sh`.

## 6. Kiểm chứng

- **Công cụ so sánh:** chạy selftest của mode `bursts` (CSV tự tạo, có cài sẵn lỗi) trước khi dùng thật.
- **TN1:**
  - line generator phải PASS với RX Xilinx trước;
  - mỗi kịch bản in một dòng kết quả: byte đã phát, byte mỗi RX nhận, chỗ sai khác, số byte trailer, cờ lỗi, độ trễ;
  - log nằm ở `fpga/work/exp1/`.
- **TN2:** 2a kiểm như TN1. 2b so từng pixel, và thanh ghi lỗi của hai CSI-2 RX phải bằng 0.
- **TN3:**
  - build TX và RX qua sign-off: timing đạt, `report_methodology` 0 Critical Warning, `report_cdc` 0 dòng Critical;
  - rà đặc tả theo checklist: tham số, chân, bước, tiêu chí đều có đủ;
  - cấu hình IP ghi trong đặc tả trùng cấu hình đã mô phỏng ở TN2.
- **Tổng hợp:** kết quả đưa vào plan doc v0.6.

## 7. Rủi ro và mục mở

- RTL chưa từng chạy end-to-end, nên nhiều khả năng TN1 sẽ lộ lỗi. Mỗi lỗi cần plan sửa riêng.
- XSIM có thể không dịch được vài cấu trúc SystemVerilog trong RTL. Phương án phụ: VCS với thư viện Xilinx (`compile_simlib`) 🔍.
- RX Xilinx có thể không nhận 80 Mb/s, hoặc đòi deskew khi trên 1500 Mb/s. Khi đó giới hạn dải rate theo IP 🔍.
- Mô hình `IBUFDS_DPHY` của XSIM cho LP bám theo mức HS (kết quả F2). Mô hình AFE của mình giả lập LP-00 trong lúc HS.
- Phía VEK280 cần team FPGA xác nhận 🔍: VADJ 1.2 V, đặt được 5 lane TX chung một bank, cách cắm mạch test.
- Thời gian làm mạch test.

## 8. Ngoài plan này

- Sửa RTL.
- Chạy phần cứng: team FPGA làm TN3.
- Buổi S0 với camera: không còn bắt buộc; build S0 được dùng lại làm R-X.
- Commit: chỉ làm khi bạn bảo.

## 9. Độ tin cậy

- **HIGH:** IP có sẵn, chân của hai board, trạng thái RTL (đều đã kiểm hôm nay).
- **MED:** các ước lượng thời gian; khả năng XSIM chạy được RTL mà không cần sửa.
- **LOW:** lúc nào có mạch test, và chân VEK280 cuối cùng là chân nào.
