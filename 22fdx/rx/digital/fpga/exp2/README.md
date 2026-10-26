# TN2a: TX D-PHY của AMD phát vào RX AMD và `ftel_dphy_rx`, mô phỏng XSIM

Thí nghiệm TN2a của [`../PLAN_TN2A.md`](../PLAN_TN2A.md), phần đầu của TN2 trong [`../PLAN_TN1_TN3.md`](../PLAN_TN1_TN3.md).
- TN1 ([`../exp1/README.md`](../exp1/README.md)) phát vào hai RX bằng line generator do mình viết.
- TN2a thay generator bằng TX D-PHY thật của AMD (IP `mipi_dphy` 4.3, MASTER), điều khiển ở PPI. Timing, trailer và
  dạng sóng trên pad nay là của TX AMD.
- Phần RX giữ như TN1: RX AMD, RX mình sau `IBUFDS_DPHY` hoặc `afe_model`, monitor, bộ kiểm. Phần lớn là code của
  TN1 dùng lại, không sửa.

README này là ghi chép kỹ thuật của nhóm. Cho team FPGA có hai tài liệu riêng, phủ cả TN2a và TN2b, không dùng thuật
ngữ nội bộ: [`TN2_DESCRIPTION.md`](TN2_DESCRIPTION.md) (mô tả thí nghiệm, cách chạy) và
[`TN2_REPORT.md`](TN2_REPORT.md) (báo cáo kết quả).

## 1. Mục đích

TN2a trả lời ba câu hỏi:
1. Khi TX AMD phát (continuous clock), hai RX có nhận đủ, đúng thứ tự, toàn bộ payload, không cờ lỗi, như ở TN1
   không?
2. Timing thật của TX, đo trên pad, nằm ở đâu so với D-PHY v1.1, và so với dải TN1 đã phủ?
3. Khi TX và RX chạy từ hai nguồn clock khác nhau (như hai board ở TN3), RX mình có còn cắt trailer đúng ở mọi pha
   `core_clk` không?

Kết quả TN2a dùng tiếp cho TN2b (CSI-2 TX Subsystem, chứa đúng TX này) và cho TN3.

## 2. Sơ đồ

```
 ppi_tx_drv ──PPI──► xtx: mipi_dphy 4.3 MASTER ─┐ t_clk, t_d (OBUFDS_DPHY)
 (txbyteclkhs)       (tx_core_clk riêng)        │
                                                ├─ mux +SRC=tx (mặc định) | gen
 dphy_line_gen (TN1, TX giữ reset) ─────────────┘    (+SRC=gen: kiểm pad_truth)
                                                │
                    ┌───────── xp_clk, xp_d ────┴──── clk_p, d_p (cùng giá trị, đều strong) ─────┐
                    │                                                                            │
     ┌──────────────┼───────────────────────┐                     ┌──────────────────────────────┤
     ▼              ▼                       │                     ▼                              ▼
 pad_truth:    RX AMD: mipi_dphy 4.3 SLAVE  │          IBUFDS_DPHY (+AFE=xil, mặc định)    afe_model (TN1):
 truth.txt,    (như TN1)                    │                     │  ┌──────────────────── +AFE=model;
 timing TX,       │ PPI ► xil_ppi.csv       │                     ▼  ▼                     luôn kiểm line
 byte pad so      │                         │          m_ftel_dphy_rx_wrap (RTL ASIC)      state, term_en
 với byte PPI     │                         │                     │ PPI ► ftel_ppi.csv
                  └──────── csi2_dump.py bursts: mỗi CSV so với truth.txt ────────────────────┘

Check trong bench: đầu ra LP của các buffer AMD và của các buffer trước RX mình trùng nhau ở mọi lần đổi sau 2,5 ps.
```

Mô phỏng chạy trong XSIM của Vivado 2025.2, part xcvp1902.

## 3. Các khối

**TX AMD** (module `xtx`, tạo bởi [`exp2.tcl`](exp2.tcl)):
- IP `mipi_dphy` 4.3, MASTER, SupportLevel 1, cùng rate và cùng số lane với `xrx`.
- `C_INIT` 99 µs, mức nhỏ nhất của IP. Các tham số khác để mặc định:
  - `C_LPX_PERIOD` 50 ns (TLPX đo trên pad là 55 ns);
  - `C_USE_LANE0_TXREADYHS` true: `txreadyhs` của lane 0 điều khiển mọi lane;
  - `C_EXAMPLE_SIMULATION` true, giống `xrx` của TN1.
- **Continuous clock** không phải tham số IP. Driver giữ `cl_txrequesths` = 1, giống example của AMD.
- **Timing HS** (PREPARE, ZERO, TRAIL, EXIT, CLK-*) do IP tự tính theo rate, không chỉnh được. Bench đo các timing
  này trên pad (§6).
- **Pad:** `OBUFDS_DPHY` lái strong trong LP và supply trong HS. Cả hai đều là strength "S", nên `IBUFDS_DPHY` của
  hai RX vẫn thấy cùng loại front end như ở TN1.
- **Hai điều đo được khi làm** (`../PLAN_TN2A.md` §13):
  - TX khởi động sau 380–571 µs, tuỳ rate, dù `C_INIT` = 99 µs;
  - model clock của TX cho line đúng rate danh định, bất kể chu kỳ `core_clk` của TX. Vì vậy muốn line lệch so với
    RX thì phải lệch `core_clk` của RX (`+CORE_HALF`), như TN1.

**Driver PPI** ([`ppi_tx_drv.sv`](ppi_tx_drv.sv)), chạy theo `txbyteclkhs` của TX:
- **`start_clock()`:** đặt `cl_txrequesths` = 1, chờ `cl_txclkactivehs`, rồi chờ thêm 2 µs như TN1. Nếu sau 50 µs
  `cl_txclkactivehs` chưa lên thì chờ `cl_stopstate` = 0; dòng `TB TX` ghi lại tín hiệu nào đã được dùng.
- **`burst()`:**
  - mọi lane có byte cùng bật `txrequesths` ở một cạnh, kèm byte đầu;
  - ở mỗi cạnh có `txreadyhs` = 1, lane đó nhận byte kế;
  - lane nhận byte cuối thì hạ request;
  - sau đó chờ mọi lane về `stopstate`, rồi chờ thêm `+GAP_NS` (mặc định 150 ns).
- **Đếm:** số burst đã xong, và số lane burst không rời `stopstate` (tức không vào HS).
- **`+TX_CORRUPT=<lane>,<burst>,<byte>`:** phát byte đó đảo bit, nhưng vẫn ghi giá trị gốc làm dự kiến. Chỉ dùng
  cho phép thử âm NEG-tx.
- **`+READY0=1`:** mọi lane theo `txreadyhs` của lane 0. Không kịch bản nào dùng, vì mọi `txreadyhs` của TX đã lên
  xuống cùng nhau.

**Bộ giải mã pad** ([`pad_truth.sv`](pad_truth.sv)), độc lập với cả hai RX và với `afe_model`:
- **Trạng thái line:** tự tính từ pad (LP-11 → LP-01 → LP-00 → HS → LP-11), viết riêng nhưng cùng luật với
  `afe_model`. Mỗi lần đổi đều so với trạng thái của `afe_model`; khác là lỗi.
- **Lấy mẫu:** đọc `d_p` ở cả hai cạnh của clock pad, khi clock lane và data lane đều ở HS.
- **Sync:** lần đầu 8 bit cuối (LSB trước) bằng 0xB8. HS-0 toàn bit 0, nên không thể khoá nhầm trước sync.
- **Thời điểm:**
  - t0 là thời điểm lấy bit sync đầu trừ nửa UI đo được trên chính byte sync;
  - t1 là thời điểm lấy bit payload cuối cộng nửa UI.

  Cùng nghĩa với truth của generator TN1: đầu byte sync và cuối bit payload cuối, tính bằng ps.
- **Payload:**
  - lấy N byte, với N là độ dài dự kiến của lane đó, và ghi `B <burst> <lane> <N> <t0> <t1> <hex>` vào
    `truth.txt`. Đây là format mà `csi2_dump.py bursts` đọc;
  - so với byte đã giao cho TX: byte khác là mismatch (in vị trí, tối đa 8 dòng);
  - burst có trên pad mà không có trong danh sách, có trong danh sách mà không thấy trên pad, không có sync, hay
    thiếu byte: đều là lỗi.
- **Timing TX**, min/max của từng tham số:
  - mỗi data lane: TLPX, THS-PREPARE, THS-ZERO, PREPARE + ZERO, THS-TRAIL (t1 → LP-11), THS-EXIT (LP-11 → LP-01
    kế);
  - clock lane, một lần: TLPX, TCLK-PREPARE, TCLK-ZERO, PREPARE + ZERO, TCLK-PRE.

  Mỗi tham số in một dòng `TB TXTIMING`, kèm giới hạn D-PHY v1.1 ở rate đó và nhãn `OUTSIDE` nếu ra ngoài. Phần này
  chỉ báo cáo.

**Testbench** ([`tb_exp2a.sv`](tb_exp2a.sv)):
- **Lấy nguyên từ [`../exp1/tb_exp1.sv`](../exp1/tb_exp1.sv):**
  - front end của RX mình (`IBUFDS_DPHY` cho mỗi lane và cho clock, chọn `+AFE`);
  - front check;
  - instance `m_ftel_dphy_rx_wrap` cùng các field cấu hình.

  Ba khối này được `tn2a_evidence.py` (check `copy`) so lại với TN1 ở mỗi lần kiểm chứng. Cũng lấy từ TN1, nhưng
  không thuộc check `copy`: ba nhánh `g_x` của `xrx`, hookup `afe_model`, hai `ppi_csv_mon`, các hàm payload, và
  watchdog.
- **Phần mới:**
  - `xtx` (ba nhánh theo số lane) và `tx_core_clk` (`+TX_CORE_HALF`, mặc định 2,5 ns);
  - **mux pad (`+SRC=tx|gen`):** lái hai bản pad cùng giá trị, đều bằng `assign`, nên đều strong:
    - bản `xp_*` vào `xrx` và `pad_truth`;
    - bản mang đúng tên `clk_p`/`d_p` của TN1 vào `IBUFDS_DPHY` của RX mình và `afe_model`. Nhờ vậy khối copy từ TN1
      giữ nguyên văn;
  - `ppi_tx_drv`, `pad_truth`;
  - **`+NEG_FRONT=1`:** trong HS (theo `pad_truth`), bản pad của RX mình mang strength pull, giống `neg_front.sh`
    của TN1; bản của `xrx` vẫn strong. Đây là phép thử âm của front check;
  - **`p_fe_start`:** in dòng `TB FRONT END CHECK START` với số lần so tới 2,5 ps và số lần khác trong đó, rồi đặt
    lại bộ đếm. Lý do: pad của TX rời X ở 1 ps, nên lần so các giá trị khởi tạo có thể rơi đúng bước 2 ps khi hai
    buffer đang đổi (`../PLAN_TN2A.md` §13, mục 3).
- **`+SRC=gen`:** TX bị giữ reset, generator của TN1 lái pad, và ghi truth riêng vào `truth_gen.txt`.
- **Trình tự một run:**
  1. nhả reset;
  2. chờ `init_done` của TX, của RX AMD và của RX mình;
  3. bật monitor;
  4. khởi động clock lane;
  5. phát các burst. Mỗi burst được ghi vào `expected.txt` và đưa vào danh sách dự kiến của `pad_truth` trước khi
     phát;
  6. chờ xả, như TN1;
  7. in kết quả.
- **Dòng kết quả:**
  - giữ đúng format TN1: `TB DONE`, `TB FRONT END CHECK`, `AFE`, `TB FTEL CFG`;
  - thêm: `TB FRONT END CHECK START`, `TB TX CFG`, `TB TX`, `TB PADS` (kèm `TB PADS MISMATCH`), `TB TXTIMING`.
- Danh sách plusarg nằm ở đầu file.

**Dùng lại, không sửa:**
- từ `../exp1/`: [`dphy_line_gen.sv`](../exp1/dphy_line_gen.sv), [`afe_model.sv`](../exp1/afe_model.sv),
  [`ppi_csv_mon.sv`](../exp1/ppi_csv_mon.sv), [`cfg_for_rate.py`](../exp1/cfg_for_rate.py), và bộ giải mã của
  [`tn1_evidence.py`](../exp1/tn1_evidence.py) (import);
- [`../tools/csi2_dump.py`](../tools/csi2_dump.py), mode `bursts`: truth cùng format, và luật ghép theo thời gian
  dùng t0/t1 của `pad_truth`;
- RTL `logical/` và `config/`.

**Chạy và kiểm** ([`run_exp2.sh`](run_exp2.sh), [`tn2a_evidence.py`](tn2a_evidence.py)): xem §7 và §9.

## 4. Điều kiện so sánh

**Giống TN1** ([`../exp1/README.md`](../exp1/README.md) §4):
- hai RX nhận đúng cùng một waveform, cùng lúc, cùng `core_clk`;
- cả hai đứng sau cùng một front end, và bench kiểm điều này ở mọi run;
- mỗi file CSV được so với cùng một truth bằng `csi2_dump.py bursts`, với cùng các luật (số burst, payload, thời
  gian, cờ, ngoài burst, trailer).

**Khác TN1:**
- **Truth lấy từ pad** (`pad_truth`), không lấy từ nguồn phát. Vì vậy cùng một cách lấy truth áp được cho cả TX AMD
  lẫn generator.
- **`pad_truth` được kiểm bằng generator đã kiểm ở TN1** (E2a-0): truth giải từ pad phải trùng truth của generator
  từng byte, t0/t1 lệch không quá 1 ps.
- **Byte trên pad được so với byte đã giao cho TX** ở mọi burst. Phép so này độc lập với cả hai RX.

**Một run PASS khi cả hai file sau đều PASS:**
- `check.txt` (`csi2_dump.py bursts`):
  - cả hai capture 0 lỗi;
  - RX AMD không giới hạn trailer;
  - RX mình tối đa `tmax` của HAS Table 4-7 không nhiễu: 4 byte ở 260 Mb/s, 6 ở 400, 0 từ 600;
  - timing ở PPI theo HAS Table A-2 (thêm ngày 2026-10-26): ở mỗi lane burst `rxsynchs` High đúng một sample,
    cùng cycle với byte payload đầu ở RX mình (C6) và trước byte đầu một cycle ở RX AMD; trong mỗi burst, byte thứ
    k tới trên các lane lệch nhau tối đa 6 byte clock (C10, ngân sách của controller CSI).
- `tbcheck.txt` (`tn2a_evidence.py tbcheck`), mỗi mục một dòng:

  | Mục | Đạt khi |
  |---|---|
  | `done` | run kết thúc `TB DONE OK` |
  | `pads` | `pad_truth` giải đủ mọi lane burst trong `expected.txt`, không thừa, có sync, đủ byte; 0 mismatch; trạng thái line trùng `afe_model` ở mọi lần đổi |
  | `front` | đầu ra LP của hai bộ buffer trùng nhau ở mọi lần đổi sau 2,5 ps; có dòng `TB FRONT END CHECK START` |
  | `afe` | `afe_model` không lỗi trạng thái; `term_en` không trễ, không thiếu |
  | `tx` | (nguồn TX) TX làm xong mọi burst, mọi lane burst đều rời `stopstate` |
  | `padtruth` | (nguồn generator) `truth.txt` trùng `truth_gen.txt` |

**Chỉ ghi nhận, không tính lỗi:** số byte trailer của RX AMD, độ trễ của byte payload cuối, thời điểm `stopstate`,
và timing TX (có nhãn `OUTSIDE` nếu ra ngoài giới hạn).

**Vẫn khác do thiết kế**, như TN1: deserializer (AMD dùng XPHY, mình dùng RTL của mình), cách bật HS receiver, cấu
hình (AMD để mặc định của IP, mình dùng model HAS), và trailer (RX AMD giữ, RX mình cắt).

## 5. Các test

Payload mặc định như E1-1: độ dài 1, 2, 3, 4, 5, 8, 16, 64, 256, 1024 byte, mỗi độ dài một lần, mẫu `counter`.

| ID | Rate (Mb/s), lane | Tham số | Mục đích |
|---|---|---|---|
| E2a-0a | 1440, 4 | `+SRC=gen` | Kiểm `pad_truth` bằng generator, với các độ dài của E1-1 |
| E2a-0b | 1440, 4 | `+SRC=gen +LENS=1,4,64,256 +TRAIL=min +EXIT=min +LPX=min` | Như trên, ở góc của E1-3c |
| E2a-0c | 1440, 4 | `+SRC=gen +UNEVEN=1 +LENS=2,3,5,9,65,257` | Như trên, lane kết thúc lệch nhau |
| E2a-1 | 1440, 4 | mặc định | Cơ bản. RX AMD phải đạt trước, để chứng minh hookup TX và truth |
| E2a-2a | 1440, 4 | `+PATTERN=prbs9 +LENS=1,2,3,8,64,256,1024 +REPEAT=2` | Như E1-2a: dữ liệu ngẫu nhiên |
| E2a-2b | 1440, 4 | `+PATTERN=synclike +LENS=4,8,16,64,256,1024` | Như E1-2b: payload giống sync |
| E2a-2c | 1440, 4 | `+UNEVEN=1 +LENS=2,3,5,9,65,257` | Như E1-2c: lane 2–3 ít hơn 1 byte, lane 0 dài nhất |
| E2a-3 | 1440, 4 | `+GAP_NS=0 +LENS=1,4,64,256 +REPEAT=2` | Burst kế được request ngay khi về `stopstate`: THS-EXIT nhỏ nhất của TX |
| E2a-4a | 260, 4 | `+TIMEOUT_US=3000`; trailer RX mình ≤ 4 | Rate thấp nhất của TX |
| E2a-4b/c | 800 / 1500, 4 | mặc định | Phủ dải R1 |
| E2a-4d/e | 1440, 2 / 1 | mặc định | Số lane |
| E2a-5 (16 run) | 260, 400, 600, 800, 1000, 1200, 1440, 1500; 4 | `+LENS=1,2,3,4,5,8,16,64,256 +REPEAT=6`; `+CORE_HALF=2.501` (`_slow`) và `2.499` (`_fast`); trailer RX mình ≤ `tmax` | EoT với trail thật của TX, LP-11 rơi vào mọi pha `core_clk` |
| `M_*` (29 run) | như trên | thêm `+AFE=model` | Bộ phụ: RX mình sau `afe_model` (LP-00 trong HS như silicon) |
| NEG-tx | 1440, 4 | `+TX_CORRUPT=1,3,0` | Check byte trên pad phải báo đúng 1 mismatch, run phải FAIL, trong khi hai RX vẫn khớp pad |
| NEG-front | 1440, 4 | `+NEG_FRONT=1` | Front check phải đếm ra khác biệt |

E2a-5 có 54 burst mỗi run, tức 216 lane burst; hai chiều lệch cộng lại là 432 lane burst mỗi rate, bằng một ô
E1-5 của TN1.

## 6. Kết quả lần chạy 2026-10-22

**60/60 run ra đúng kỳ vọng.**
- 29/29 kịch bản PASS cho cả hai RX.
- Bộ phụ `M_*`: 29/29 PASS.
- Hai phép thử âm FAIL đúng chỗ đã cài.
- `tn2a_evidence.py evidence`: **PASS (10/10 checks)** (§7).
- **2026-10-26, kiểm lại không mô phỏng** (`run_exp2.sh recheck`) với timing ở PPI (§4): 60/60 run giữ nguyên kết
  quả. Ở mọi lane burst, `rxsynchs` rộng một sample, cùng cycle với byte đầu ở RX mình, trước một cycle ở RX AMD;
  lệch giữa các lane 0 byte clock. Riêng NEG-front không có số đo, vì PPI của RX mình ở đó hỏng có chủ ý.

Kết quả chạy trên RTL của commit `5fa890b` (HAS v0.16). `logical/` và `config/` không đổi so với commit đó.

**Trả lời ba câu hỏi ở §1:**
1. **Có.** Với TX thật, cả hai RX nhận đủ, đúng thứ tự, toàn bộ payload, 0 cờ lỗi. Điều này đúng ở 8 rate từ 260 tới
   1500 Mb/s, ở 1, 2 và 4 lane, và cả với lane kết thúc lệch nhau, payload giống sync, PRBS-9, burst sát nhau.
2. **Mọi timing của TX đo trên pad đều nằm trong giới hạn D-PHY v1.1, ở cả 8 rate** (`run_exp2.sh txtiming`: 0 giá
   trị `OUTSIDE`). Hai chỗ TN1 chưa phủ, nay đã được phủ bằng TX thật, và RX mình đạt:
   - TCLK-PREPARE 81,9–88,5 ns (TN1 chỉ thử 66 ns);
   - THS-PREPARE ở 260 Mb/s là 95,6–103,0 ns, gần mức max 108,1 ns (TN1 thử giá trị giữa khoảng ở rate này).
3. **Có.** E2a-5 cho `core_clk` của hai RX lệch ±400 ppm so với line của TX. Ở cả 8 rate, RX mình nhận đủ 432/432
   lane burst ở cả hai front end, và trailer trong giới hạn.

**Trailer và độ trễ.** Trailer là số byte mỗi burst; với `afe_model`, số trong ngoặc là số burst có trailer. Độ trễ
là của byte payload cuối.

| Rate (Mb/s) | Kịch bản | Trailer: AMD | Trailer: RX mình sau `IBUFDS_DPHY` | Trailer: RX mình sau `afe_model` | Giới hạn | Độ trễ: AMD | Độ trễ: RX mình |
|---|---|---|---|---|---|---|---|
| 260 | E2a-4a, E2a-5 | 2 | 0 | 0–2 (20/40 ở E2a-4a; 216/432 ở E2a-5) | 4 | 167 ns | 1117 ns |
| 400 | E2a-5 | 4 | 0 | 0 | 6 | 99 ns | 741 ns |
| 600 | E2a-5 | 7 | 0 | 0 | 0 | 66 ns | 484 ns |
| 800 | E2a-4b, E2a-5 | 9–10 | 0 | 0 | 0 | 50 ns | 363–366 ns |
| 1000 | E2a-5 | 12–13 | 0 | 0 | 0 | 40 ns | 295 ns |
| 1200 | E2a-5 | 15 | 0 | 0 | 0 | 33 ns | 244 ns |
| 1440 | E2a-1…E2a-3, E2a-4d/e, E2a-5 | 17–18 | 0 | 0 | 0 | 28 ns | 202–205 ns |
| 1500 | E2a-4c, E2a-5 | 18–19 | 0 | 0 | 0 | 26 ns | 195–198 ns |
| 1440, generator | E2a-0a/b/c | 14–17 | 0 | 0 | 0 | 28–32 ns | 201–206 ns |

**Timing TX trên pad** (ns; min..max trên mọi run từ TX ở rate đó). Bảng đủ, kèm giới hạn ở từng rate, in bằng
`run_exp2.sh txtiming`:

| Tham số | 260 | 400 | 600 | 800 | 1000 | 1200 | 1440 | 1500 | TN1 đã phủ ở 1440 |
|---|---|---|---|---|---|---|---|---|---|
| TLPX (data, clock) | 55,0 | 55,0 | 55,0 | 55,0 | 55,0 | 55,0 | 55,0 | 55,0 | 50 / 75 |
| THS-PREPARE | 95,6–103,0 | 87,3 | 86,6–89,9 | 77,3 | 77,9–81,9 | 79,9–83,2 | 76,3–81,3 | 75,9–80,9 | 42,8 / 66 / 89,2 |
| THS-PREPARE + THS-ZERO | 300,9–305,5 | 274,4 | 264,6–268,0 | 223,2 | 210,6–214,6 | 223,8–227,1 | 212,9–217,9 | 207,1–212,1 | 151,9 / 182 |
| THS-TRAIL | 85,9 | 82,9 | 81,9 | 84,2 | 83,3 | 82,7 | 80,1 | 76,9 | 62,8 / 75,3 / 107,8 |
| THS-EXIT | 322,8–327,4 | 307,7 | 301,8–305,1 | 287,7 | 287,1–291,1 | 285,1–291,8 | 137,6–290,4 | 285,1–291,8 | 100 / 150 |
| TCLK-PREPARE | 86,8 | 87,3 | 88,2 | 87,3 | 81,9 | 86,6 | 88,5 | 88,2 | 66 |
| TCLK-PREPARE + TCLK-ZERO | 379,8 | 375,7 | 347,1 | 363,8 | 343,1 | 377,6 | 375,5 | 358,4 | 360 |

- THS-EXIT phụ thuộc `+GAP_NS`, tức thời gian bench chờ sau `stopstate`. Giá trị 137,6 ns là của E2a-3, khi burst kế
  được request ngay; các run khác chờ 150 ns.
- TCLK-PRE khoảng 2,05–2,18 µs, vì bench chờ 2 µs sau khi clock chạy rồi mới phát burst đầu.
- THS-TRAIL không đổi trong một rate, vì TX không có jitter trail và không có nhiễu.

**Khởi động TX** (`init_done`, `C_INIT` = 99 µs):

| Rate (Mb/s) | 260 | 400 | 600 | 800 | 1000 | 1200 | 1440 | 1500 |
|---|---|---|---|---|---|---|---|---|
| `init_done` của TX (µs) | 395,2 | 570,5 | 386,2 | 570,5 | 392,9 | 386,2 | 383,3 | 380,5 |

**Đọc kết quả:**
- **Payload:** khi TX thật phát vào, phần digital của RX mình nhận đúng mọi payload như RX AMD, ở mọi rate và mọi
  số lane.
- **Trailer:**
  - RX AMD giữ 2–19 byte tuỳ rate. RX mình sau `IBUFDS_DPHY` cắt hết ở mọi rate. Sau `afe_model` cũng cắt hết, trừ
    260 Mb/s (0–2 byte, dưới giới hạn 4).
  - Ở 1440 Mb/s, RX AMD giữ 17–18 byte với TX, so với 14–17 byte với generator. Lý do: trail của TX (80,1 ns) dài
    hơn trail mặc định của generator (75,3 ns) khoảng một byte (5,56 ns).
- **Độ trễ:** RX mình trễ hơn RX AMD 6,7–7,5 lần, giống TN1, do delay line cần cho việc cắt trailer.

Chi tiết từng run nằm trong `fpga/work/exp2/<tên>/` (gitignored): `check.txt`, `tbcheck.txt`, `tb.txt`.

## 7. Kiểm chứng: vì sao tin được kết quả

Sáu lớp giống TN1 ([`../exp1/README.md`](../exp1/README.md) §7). [`tn2a_evidence.py`](tn2a_evidence.py) kiểm lại tự
động từ output trong `fpga/work/exp2`. Nó chỉ đọc các run `E2a-*`, `M_E2a-*` và `NEG-*`; các run `S0_*` và `DBG-*`
là run thăm dò, không thuộc tập kiểm.

```bash
python3 fpga/exp2/tn2a_evidence.py evidence      # mỗi check một dòng PASS/FAIL, rồi EVIDENCE: PASS/FAIL
python3 fpga/exp2/tn2a_evidence.py evselftest    # script kiểm chứng tự thử trên lỗi cài sẵn (§7.7)
```

Kết quả ngày 2026-10-22: **EVIDENCE: PASS (10/10 checks)**. Ngày 2026-10-26, sau khi thêm timing ở PPI vào cả
`csi2_dump.py` lẫn bộ giải mã của `tn1_evidence.py`: vẫn **PASS (10/10 checks)**.

| Check | Kiểm gì | Kết quả 2026-10-22 |
|---|---|---|
| `checker` | Selftest của `csi2_dump.py`: tìm được các lỗi cài sẵn; capture sạch thì đạt | PASS |
| `decode` | Giải mã lại mọi capture bằng bộ giải mã của `tn1_evidence.py` (viết riêng, không chung code với `csi2_dump.py`), so với `truth.txt`, kể cả timing ở PPI (§4); kết quả phải trùng `check.txt`. Bộ giải mã tự thử trên capture giả trước | 120/120 capture |
| `runs` | Đủ 60 run (29 kịch bản, 29 `M_*`, 2 phép thử âm); mọi run kết thúc `TB DONE OK` với một dòng truth cho mỗi burst và lane; mọi kịch bản PASS cả `check.txt` lẫn `tbcheck.txt` | 60/60 run |
| `tx` | Ở mọi run từ TX, byte trên pad bằng byte đã giao cho TX. NEG-tx: đúng một mismatch, đúng chỗ đã cài, và là mục duy nhất của `tbcheck` hỏng; hai RX vẫn khớp pad | 54 run + NEG-tx |
| `padtruth` | Mọi run từ generator: `truth.txt` trùng `truth_gen.txt`; selftest của `tbcheck` và `padtruth` (13 ca) | 6 run, lệch 0 ps |
| `front` | Đầu ra LP của hai bộ buffer trùng nhau ở mọi lần đổi sau 2,5 ps; RX mình sau `IBUFDS_DPHY` trừ khi đặt `+AFE=model`. NEG-front phải đếm ra khác biệt, trong khi RX AMD vẫn đạt | 59 run, 2 812 162 lần so, 0 khác; NEG-front 25 744 / 32 674 |
| `afe` | `afe_model` không lỗi trạng thái; `term_en` không trễ, không thiếu (trừ NEG-front, §7.6) | 59/59 run |
| `config` | Cấu hình RX mình đúng giá trị model HAS ở rate đó, hoặc giá trị kịch bản đặt | 60/60 run |
| `sources` | Hash nguồn ghi trong `args.txt` của từng run bằng hash nguồn hiện tại (RTL theo `filelist.f`, ba khối của `exp1/`, `exp2/*.sv`) | 60/60 run, `4029acbab7d90fa3` |
| `copy` | Ba khối `tb_exp2a.sv` lấy từ `tb_exp1.sv` vẫn trùng nguyên văn, không kể comment và dòng trống | 29, 15, 59 dòng code trùng |

### 7.1 Lớp 1: tín hiệu phát vào có đúng không?

- **TX là IP của AMD,** và RX AMD nhận đúng mọi burst ở cả 60 run. Đây là điều kiện tiên quyết của plan: nếu hookup
  TX, truth hay phép ghép sai thì RX AMD đã hỏng trước.
- **Byte trên pad bằng byte đã giao cho TX** ở mọi burst của 54 run từ TX. Phép so dùng `pad_truth`, độc lập với cả
  hai RX.
- **`pad_truth` được kiểm bằng generator đã kiểm ở TN1** (E2a-0 và `M_E2a-0`): 160 lane burst trùng từng byte, t0 và
  t1 lệch đúng 0 ps.
- **Hai cách tính trạng thái line độc lập cho cùng kết quả:** trạng thái line của `pad_truth` trùng của `afe_model`
  ở mọi lần đổi, trong mọi run.
- **Timing TX được đo và so với công thức D-PHY v1.1** ở mọi run: 0 giá trị ra ngoài.

### 7.2 Lớp 2: bộ kiểm có biết báo FAIL không?

| Bằng chứng | Kết quả |
|---|---|
| Selftest của `csi2_dump.py` | Bắt đủ các lỗi cài sẵn, kể cả ca chỉ sai thời gian |
| NEG-tx: TX phát byte 0 của burst 3, lane 1 đảo bit | `pads` FAIL với đúng 1 mismatch: `8f` trên pad thay cho `70`. Hai RX vẫn PASS so với pad, vì truth là pad |
| NEG-front: buffer trước RX mình thấy pull trong HS | `front` FAIL: 25 744 / 32 674 lần so khác (§7.6) |
| Selftest của `tbcheck` và `padtruth` (13 ca, gồm thiếu dòng START, lệch t0 2 ps, mất một dòng truth) | Mỗi lỗi cài sẵn làm hỏng đúng mục của nó; lệch 1 ps vẫn đạt |
| Output trước khi thêm `p_fe_start` (run S2 đầu tiên; đã bị chạy đè, nên số liệu chỉ còn ghi ở đây) | `evidence` FAIL ở 4 check: `front` (thiếu dòng START), kéo theo `tx` (NEG-tx hỏng thêm mục `front`), `sources` (hash cũ) và `runs` (thiếu run) |

### 7.3 Lớp 3: PASS có được tính đúng không?

- `tn2a_evidence.py` giải mã lại 120/120 capture bằng bộ giải mã của `tn1_evidence.py`. Bộ giải mã đó không dùng chung
  dòng code nào với `csi2_dump.py`, và có cùng luật ghép theo thứ tự và theo thời gian.
- Kết quả trùng `check.txt` ở cả 120 capture: số burst có payload đúng, khoảng trailer, và kết luận đạt/hỏng.
- `recheck` kiểm lại mọi output bằng công cụ hiện tại, không mô phỏng lại (6 s).
  - Kết quả: 124 file `check.txt` và `tbcheck.txt`, chỉ 1 file đổi: `DBG-E2a-4d/tbcheck.txt`.
  - Đó là run debug chạy trước khi thêm `p_fe_start`. Nay nó được báo đúng là thiếu dòng START.

### 7.4 Lớp 4: thứ được test có đúng là thứ trong repo không?

- **Hash nguồn theo từng run:** `run_exp2.sh` ghi hash của build vào `args.txt` của mỗi run, và check `sources` so
  từng run với nguồn hiện tại. Cách này chặt hơn TN1, vốn chỉ so hash của build: một run chạy trước lần sửa nguồn cuối
  sẽ bị bắt.
- **RTL không đổi so với commit `5fa890b`.**
- **Cấu hình mỗi run đúng model HAS ở rate đó.** Ví dụ `eot_skip_bytes` 13 ở 1440 Mb/s.
- **Khối copy không lệch TN1** (check `copy`).
- **Không run nào dừng giữa chừng:** mọi run kết thúc `TB DONE OK`, và truth có đủ burst × lane.

### 7.5 Lớp 5: kết quả EoT có phải do may không?

- **Đã thử lệch ở phía TX, nhưng không có tác dụng.** Model clock của TX cho line đúng rate danh định bất kể
  `core_clk` của TX. S0 chứng minh: lệch 100 ppm cho pad trùng tới từng ps (`../PLAN_TN2A.md` §13).
- **Vì vậy E2a-5 lệch `core_clk` của hai RX ±400 ppm,** như E1-5. Với RX, điều cần là pha tương đối giữa LP-11 và
  `core_clk`, nên hai cách tương đương.
- **Phủ:** mỗi rate 432 lane burst cho mỗi RX và mỗi front end, LP-11 rơi vào mọi pha `core_clk`.
- **Kết quả:** RX mình 0 trailer từ 400 Mb/s. Ở 260 Mb/s, 0–2 byte sau `afe_model`, dưới giới hạn 4.
- **Giới hạn:** trail của TX không đổi trong một rate, nên E2a-5 phủ mọi pha nhưng không phủ các độ dài trail khác
  nhau. Các độ dài trail (min, mặc định, max, jitter, nhiễu) đã được E1-5 của TN1 phủ.

### 7.6 Lớp 6: hai RX có thật cùng front end không?

- **Kiểm ở mọi run** (check `front`): 59 run, 2 812 162 lần so đầu ra LP của hai bộ buffer, 0 khác.
- **Lần so trước 2,5 ps không tính, nhưng được in ra.**
  - Ở 4 run có lane không dùng (E2a-4d, E2a-4e và `M_` của chúng), lần so các giá trị khởi tạo rơi đúng vào bước
    2 ps. Lúc đó pad của TX vừa rời X ở 1 ps, và hai buffer đang đổi.
  - Mỗi run có đúng 1 lần so như vậy, và lần đó khác. Mọi lần so sau đều trùng.
  - Bằng chứng: `fpga/work/exp2/DBG-E2a-4d/tn2a.vcd`. Cách xử lý do bạn chọn ngày 22/10 (`../PLAN_TN2A.md` §13, mục 3).
- **Check này biết báo FAIL** (NEG-front): 25 744 / 32 674 lần so khác, `front` FAIL, RX AMD vẫn đạt.
- **Tác dụng phụ của NEG-front, chỉ ghi nhận:** RX mình 0/40 burst, `term_en` thiếu 36 lần. Đây không phải phát hiện
  RTL.
  - Model `IBUFDS_DPHY` tính strength trong một `always @(*)` (`$sformat("%v", I)`). Trong XSIM, khối này không chạy
    lại khi chỉ strength đổi mà giá trị pad giữ nguyên (VCD dưới đây).
  - Bench nhả pull 1 ps sau khi pad lên LP-11, khi giá trị pad không đổi nữa. Vì vậy buffer của RX mình giữ LP 00 cho
    tới request kế, RX mình không bao giờ thấy LP-11 và kẹt trong HS sau burst đầu.
  - Ở `neg_front.sh` của TN1, strength đổi cùng bước với pad, nên RX mình vẫn đạt.
  - Bằng chứng (`fpga/work/exp2/DBG-NEG-front/tn2a.vcd`, lane 0, sau burst đầu):

    | Thời điểm so với LP-11 | Pad | Pull | LP ra: AMD | LP ra: RX mình |
    |---|---|---|---|---|
    | −1 ns | 10 (trail) | bật | 10 | 00 |
    | +1 ns, +100 ns, +285 ns | 11 | tắt | 11 | 00 |

  - Vì vậy `evidence` chỉ in kết quả của RX mình và của `afe` ở NEG-front, không chấm.

### 7.7 Kiểm chính `tn2a_evidence.py`

`evselftest` chạy `evidence` trên các run thật, mỗi lần cài một lỗi:
- các run được link vào một thư mục tạm;
- riêng run bị sửa được chép sang thư mục tạm rồi mới sửa;
- output thật không bị đụng.

Mỗi lỗi phải làm hỏng đúng các check ghi dưới đây, không thừa, không thiếu.

| Lỗi cài | Check phải hỏng | 2026-10-22 |
|---|---|---|
| Không lỗi | không check nào | đúng |
| Đảo 1 bit payload trong `ftel_ppi.csv` của E2a-1 | `decode` | đúng |
| `rxsynchs` High 3 cycle trong `ftel_ppi.csv` của E2a-1 (lỗi tester team FPGA cài, thêm 2026-10-26) | `decode` | đúng (2026-10-26) |
| `rxsynchs` dời tới byte payload thứ ba (như trên) | `decode` | đúng (2026-10-26) |
| Cả lane 3 trễ 8 cycle (như trên) | `decode` | đúng (2026-10-26) |
| Đổi chỗ cài của NEG-tx trong `args.txt` | `tx` | đúng |
| Đảo 1 bit trong `truth_gen.txt` của E2a-0a | `padtruth`, `runs` | đúng |
| Một khác biệt front end trong `tb.txt` của E2a-1 | `front`, `runs` | đúng |
| Một `term_en` trễ | `afe`, `runs` | đúng |
| `eot_skip_bytes` khác model | `config` | đúng |
| Hash nguồn khác | `sources` | đúng |
| Thiếu run E2a-3 | `runs` | đúng |
| Sửa một dòng của instance wrap trong bản copy `tb_exp2a.sv` | `copy` | đúng |

Kết quả: `evselftest: PASS`, 11 s (2026-10-22, 10 lỗi); 2026-10-26, 13 lỗi: PASS, 3 s (kết quả giải mã của mỗi
capture được giữ lại giữa các lần cài lỗi). Riêng `checker` không có ca cài lỗi, vì bản thân nó là selftest của
`csi2_dump.py`.

### 7.8 Giới hạn của phần kiểm chứng

1. **Front end chung vẫn là model mô phỏng của AMD.** Trong HS, LP đổi theo data, trong khi silicon cho LP-00. Bộ
   phụ `M_*` phủ trường hợp LP-00, và RX mình đạt ở cả hai.
2. **TX và RX AMD trong XSIM là model mô phỏng của AMD,** không phải phần cứng. Model clock của TX bỏ qua chu kỳ
   `core_clk` của nó. TN3 trên board sẽ xác nhận.
3. **Timing của TX không chỉnh được,** nên TN2a chỉ thấy một điểm timing ở mỗi rate. Các góc timing đã được TN1 phủ.
4. **TX trong mô phỏng không có skew giữa lane** và không có jitter. TN1 đã phủ skew ±0,2 UI.
5. **RTL mô phỏng zero-delay,** không có metastability.
6. **`stopstate`** có ghi trong CSV nhưng không kiểm.

**Độ tin cậy:**
- HIGH:
  - PASS là thật trong điều kiện đã mô phỏng;
  - timing TX là số đo trên pad;
  - hai RX cùng front end (kiểm ở mọi run, có phép thử âm).
- MED: hai điều đọc từ VCD và từ mã nguồn model (race lúc t = 2 ps, và model không chạy lại khi strength đổi), vì
  mỗi điều mới được xem ở một run debug.
- LOW: chuyển kết luận sang silicon, vì TX, RX AMD và front end đều là model.

## 8. TN2a không kiểm những gì

- **Skew giữa lane và pha clock:** TX trong mô phỏng không có skew. TN1 đã phủ ±0,2 UI.
- **Góc timing của TX:** IP không cho chỉnh. TN1 đã phủ các góc bằng generator.
- **ULPS, escape mode, deskew, non-continuous clock.**
- **Packet CSI-2:** thuộc TN2b (CSI-2 TX Subsystem).
- **Hiệu ứng analog:** pad chỉ là mức logic.
- **80 Mb/s và các rate ngoài R1:** TX chạy thấp nhất 260 Mb/s.
- **Lệch clock ở phía TX:** model clock của TX không cho lệch. Thay bằng lệch ở phía RX (§7.5).

## 9. Cách chạy

Chạy từ thư mục gốc của repo. Output nằm ở `fpga/work/exp2/<tên kịch bản>/` (gitignored): `truth.txt`,
`expected.txt`, `xil_ppi.csv`, `ftel_ppi.csv`, `xsim.log`, `tb.txt`, `args.txt`, `check.txt` và `tbcheck.txt`.

```bash
fpga/exp2/run_exp2.sh E2a-1                # cơ bản, 1440 Mb/s, 4 lane (~1,5 phút, chưa kể build)
fpga/exp2/run_exp2.sh all                  # E2a-0…E2a-5, rồi bảng kết quả
fpga/exp2/run_exp2.sh E2a-5 400 600        # E2a-5 ở một số rate (mỗi rate 2 run, ~4 phút)
fpga/exp2/run_exp2.sh E2a-4 a b            # một phần của E2a-4
fpga/exp2/run_exp2.sh model                # bộ phụ M_*: mọi kịch bản, RX mình sau afe_model
fpga/exp2/run_exp2.sh model E2a-5 1440     # bộ phụ, một nhóm hoặc một số rate
fpga/exp2/run_exp2.sh neg                  # NEG-tx và NEG-front
fpga/exp2/run_exp2.sh run 1440 4 <tên> +PATTERN=prbs9 +LENS=1,8,64   # một kịch bản tự chọn
fpga/exp2/run_exp2.sh summary              # dòng kết quả (check.txt | tbcheck.txt) của mọi run
fpga/exp2/run_exp2.sh recheck              # kiểm lại mọi output bằng công cụ hiện tại (~6 s, không mô phỏng)
fpga/exp2/run_exp2.sh txtiming             # bảng timing TX trên pad theo rate, kèm giới hạn D-PHY v1.1
fpga/exp2/run_exp2.sh evidence             # kiểm chứng kết quả (§7)
python3 fpga/exp2/tn2a_evidence.py evselftest   # kiểm chính script kiểm chứng (§7.7)
EXP2_DEBUG=typical fpga/exp2/run_exp2.sh run 1440 4 DBG-x +VCD=1     # build có debug, ghi tn2a.vcd
```

- **Build:** mỗi tổ hợp rate × số lane cần một build. Lần đầu mất khoảng 3 phút cho Vivado và 4 phút cho compile.
  Khi chỉ testbench đổi thì compile lại trong vài chục giây.
- **Thời gian chạy:** một run từ TX mất 85–130 s ở 4 lane và khoảng 55 s ở 1 hoặc 2 lane, vì TX khởi động 380–571 µs
  mô phỏng. Một run `+SRC=gen` mất 12–15 s.
- **Chạy song song:** các lệnh trên các build khác nhau chạy song song được; hai lệnh không được dùng chung một build
  cùng lúc. Lần chạy 2026-10-22 dùng 3 tiến trình, mỗi tiến trình giữ riêng các build của mình. Kết quả: 10 build
  (4 build mới) và 60 run xong trong 40 phút; tổng thời gian mô phỏng 5 573 s.
- Danh sách plusarg nằm ở đầu [`tb_exp2a.sv`](tb_exp2a.sv).
