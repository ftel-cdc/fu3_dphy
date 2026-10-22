# Plan: TN2a — TX D-PHY thật của AMD phát vào hai RX, mô phỏng XSIM (2026-10-22)

> Repo `fu3_dphy`, branch `dev`, sau commit `5fa890b`; thư mục `22fdx/rx/digital/fpga/`.
> Ký hiệu: ✅ đã kiểm hôm nay (đọc file hoặc dữ liệu đã lưu) · ⚠️ ước lượng hoặc giả định · 🔍 kiểm khi làm.
> Bạn duyệt plan này ngày 2026-10-22.

## 0. Context

- TN1 đã xong:
  - 113/113 kịch bản PASS cho cả hai RX, so công bằng sau `IBUFDS_DPHY`, RTL theo HAS v0.16;
  - bản bàn giao cho team FPGA đã push (`5fa890b`).
- Bạn chốt (22/10): từ nay làm ở repo `fu3_dphy`, tiếp TN2. Bạn chọn ba điểm sau rồi duyệt plan này:
  - D1: làm 2a trước; 2b và 2c mỗi phần có plan riêng sau;
  - D2: bench mới trong `exp2/`, TN1 giữ nguyên;
  - D3: tài liệu bàn giao TN2 viết sau khi xong 2a và 2b.
- Khác TN1 ở chỗ: tín hiệu trên pad (timing, trailer, dạng sóng) là của TX D-PHY thật của AMD, không phải của
  generator do mình viết. Kết quả TN2a dùng tiếp cho TN2b (CSI-2 TX SS chứa đúng TX này) và cho TN3.

## 1. Câu hỏi TN2a trả lời

1. Khi TX AMD (`mipi_dphy` 4.3 MASTER, continuous clock) phát, hai RX có nhận đủ, đúng thứ tự, toàn bộ payload,
   không cờ lỗi như ở TN1 không?
2. Timing thật của TX, đo trên pad, nằm ở đâu so với D-PHY v1.1, và so với dải mà TN1 đã phủ?
3. Khi TX và RX chạy từ hai nguồn clock khác nhau (như hai board ở TN3), RX mình có còn cắt trailer đúng ở mọi
   pha `core_clk` không?

## 2. Dữ kiện đã kiểm hôm nay ✅

**Từ IP Vivado 2025.2** (`mipi_dphy_v4_3`, xgui và component.xml):
- Continuous clock không phải tham số IP: phía PPI giữ `cl_txrequesths` = 1, như example của AMD làm.
- MASTER trên xcvp1902 chạy 260 tới 2538/2594 Mb/s, tuỳ speed grade.
- `C_INIT` 99 µs–1 ms (MASTER mặc định 1 ms); `C_LPX_PERIOD` 50–100 ns.
- Các timing HS (PREPARE, ZERO, TRAIL, EXIT, CLK-*) do IP tự tính, không chỉnh được.
- `C_USE_LANE0_TXREADYHS` mặc định true, nghĩa là "dùng `txreadyhs` của lane 0 cho mọi lane".
- `C_EXAMPLE_SIMULATION` mặc định true (rút ngắn timer khi mô phỏng). `xrx` của TN1 cũng dùng true.
- Cổng (SupportLevel 1):
  - vào: `core_clk`, `core_rst`;
  - ra: `txbyteclkhs`, `init_done`, `cl_txclkactivehs`, `cl_stopstate`;
  - mỗi lane: `txrequesths`, `txreadyhs`, `txdatahs[7:0]`, `stopstate`, `enable`;
  - pad: `clk_txp/n`, `data_txp/n`.

**Từ lần chạy probe `dphy_exdes_sim` ngày 12/10** (example của RX AMD, có TX đối tác MASTER, 1440 Mb/s, 4 lane;
output nằm trong thư mục work của nhóm, git bỏ qua; `f2.vcd` được đọc lại ngày 22/10):
- **Pad:** chỉ có mức logic 0/1; Dp và Dn đổi cùng một ps; trong HS không có LP-00 hay LP-11 nào ngắn hơn 1 ns.
- **Clock:** cạnh clock nằm giữa bit data (lệch ±347 ps, đúng nửa UI).
- **`OBUFDS_DPHY`:** lái strong khi LP và supply khi HS. Cả hai đều là strength "S", nên `IBUFDS_DPHY` của hai
  RX thấy cùng front end như ở TN1.
- **Timing đo trên pad** (giới hạn D-PHY v1.1 ở 1440 Mb/s trong ngoặc):

  | Tham số | Đo | Giới hạn | TN1 đã phủ |
  |---|---|---|---|
  | TLPX | 55,0 ns | ≥ 50 | 50 / 75 |
  | THS-PREPARE | 76,9–79,6 ns | 42,8–89,2 | 42,8 / 66 / 89,2 |
  | PREPARE + ZERO | khoảng 214 ns | ≥ 151,9 | 151,9 / 182 |
  | THS-TRAIL | 80,2 ns | 62,8–113,3 (TEOT) | 62,8 / 75,3 / 107,8 |
  | TCLK-PREPARE | 88,5 ns | 38–95 | 66 |
  | TCLK-PREPARE + ZERO | 375 ns | ≥ 300 | 360 |

- **Burst:** TX nhận burst 1 byte.
  - RX AMD giữ 18 byte trailer mỗi burst, khớp với 16–18 byte ở TN1.
  - `txreadyhs` lên khoảng 255 ns sau LP-01, ngay trước sync.
- **Khởi động:** byte clock của TX chạy từ 3,3 µs, nhưng clock lane chỉ rời LP-11 ở khoảng 384 µs (example
  đặt `C_INIT` 200 µs) ⚠️. Mỗi run TN2a vì vậy dài hơn run TN1 nhiều.
- **Model cấu hình** (`config/validate_config.py`): R1 = 80–1500 Mb/s. R2 (1792 Mb/s) không có trong RTL này,
  nên TN2a giữ 260–1500 Mb/s như TN1.

## 3. Thiết kế bench (`fpga/exp2/`)

### 3.1 Sơ đồ

```
            +SRC=tx (mặc định)                                +SRC=gen (chỉ để kiểm pad_truth, E2a-0)
ppi_tx_drv ─PPI─► xtx: mipi_dphy 4.3 MASTER ─┐               dphy_line_gen (exp1, không sửa) ─┐
  (txbyteclkhs)   (core clock riêng của TX)   └──► mux pad (assign: strong ở cả hai RX) ◄──────┘
                                                     │ CLK, D0..D3
       ┌────────────────────────┬────────────────────┼──────────────────────────┐
       ▼                        ▼                    ▼                          ▼
 pad_truth (mới):         xrx: RX AMD SLAVE    IBUFDS_DPHY → ftel_dphy_rx    afe_model (exp1):
 truth.txt, timing TX,    (như TN1)            (RTL ASIC, như TN1)           kiểm line state, term_en;
 so byte pad với PPI         │ xil_ppi.csv        │ ftel_ppi.csv              front của ftel khi +AFE=model
                             └────────── csi2_dump.py bursts: mỗi CSV so với truth.txt ──────┘
```

### 3.2 Khối mới

**`exp2.tcl`** (dựa trên `exp1.tcl`):
- Tạo `xrx` như TN1: SLAVE, `C_INIT` 99 µs.
- Tạo thêm `xtx`: `mipi_dphy` 4.3, `C_DPHY_MODE MASTER`, cùng rate và số lane, SupportLevel 1, `C_INIT` 99 µs;
  các tham số khác để mặc định.
- In một dòng `EXP2 xtx:` gồm rate, số lane, `C_LPX_PERIOD`, `C_INIT`, `C_USE_LANE0_TXREADYHS`,
  `C_EXAMPLE_SIMULATION`.
- Thêm RTL theo `logical/filelist.f`, ba khối của `exp1/` theo đường dẫn, và các file của `exp2/`.

**`ppi_tx_drv.sv`** (driver PPI TX, chạy theo `txbyteclkhs` của TX):
- `start_clock()`: `cl_txrequesths` ← 1 (continuous). Chờ clock lane chạy (`cl_txclkactivehs`; nếu cổng này
  không như kỳ vọng thì chờ `cl_stopstate` = 0) 🔍, rồi chờ thêm 2 µs như TN1.
- `burst(id, bytes[NL])`:
  - các lane có byte cùng bật `txrequesths` ở một cạnh, kèm byte đầu;
  - byte tiếp theo được đưa ra ở mỗi cạnh có `txreadyhs` = 1;
  - lane nào được nhận byte cuối thì hạ request của lane đó;
  - chờ mọi lane về `stopstate` = 1, rồi chờ thêm `+GAP_NS` (mặc định 150 ns, giống THS-EXIT mặc định của TN1).
- Đưa danh sách byte dự kiến của từng lane sang `pad_truth`.
- `+TX_CORRUPT=<lane>,<burst>,<byte>`: phát byte đó đảo bit (XOR 0xFF), nhưng vẫn ghi giá trị gốc làm dự kiến.
  Chỉ dùng cho phép thử âm.
- `+TXLOG=1`: in từng cạnh request/ready của 3 burst đầu, dùng ở S0.

**`pad_truth.sv`** (bộ giải mã pad, độc lập với cả hai RX):
- **Trạng thái line:** tự tính từ pad, cùng luật với `afe_model` nhưng viết riêng: LP-11 → LP-01 → LP-00 → HS
  cho tới LP-11. Mỗi lần đổi đều so với `in_hs` của `afe_model`; khác là lỗi.
- **Lấy mẫu:** đọc `d_p` ở cả hai cạnh của clock pad, khi lane đang ở HS.
- **Sync:** lần đầu 8 bit cuối (LSB trước) bằng 0xB8. HS-0 toàn bit 0, nên không thể khoá nhầm trước sync.
- **Thời điểm:**
  - t0 = cạnh lấy bit sync đầu − nửa UI đo được;
  - t1 = cạnh lấy bit payload cuối + nửa UI.

  Cùng nghĩa với truth của generator TN1: đầu byte sync và cuối bit payload cuối, tính bằng ps.
- **Payload:** lấy N byte, với N lấy từ danh sách dự kiến của lane đó.
  - Ghi `B <id> <lane> <N> <t0> <t1> <hex>` vào `truth.txt`, cùng format cũ, nên `csi2_dump.py` không phải sửa.
  - Byte giải được khác byte dự kiến thì đếm là TX MISMATCH. Burst có trên pad mà không có trong danh sách, hoặc
    có trong danh sách mà không xuất hiện trên pad, đều là lỗi.
- **Timing TX:** min/max của từng tham số, mỗi lane:
  - data lane: TLPX, THS-PREPARE, THS-ZERO, PREPARE + ZERO, THS-TRAIL (t1 → LP-11), THS-EXIT (LP-11 → LP-01 kế);
  - clock lane, đo một lần: TLPX, TCLK-PREPARE, TCLK-ZERO, TCLK-PRE.

  Mỗi tham số in một dòng `TB TXTIMING`, kèm giới hạn D-PHY v1.1 (công thức như `p_main` của `tb_exp1.sv`) và nhãn
  `OUTSIDE` nếu ra ngoài giới hạn. Phần này chỉ báo cáo.

**`tb_exp2a.sv`:**
- **Copy nguyên logic từ `tb_exp1.sv`:**
  - ba nhánh `g_x` của `xrx`;
  - hookup `afe_model`;
  - `IBUFDS_DPHY` trước RX mình và `TB FRONT END CHECK`;
  - instance `m_ftel_dphy_rx_wrap` cùng các field cấu hình;
  - hai `ppi_csv_mon`;
  - các hàm `make_payload`, `prbs9`, `parse_list`;
  - watchdog;
  - knob của generator dùng cho `+SRC=gen`.
- **Phần mới:**
  - `xtx` (ba nhánh theo số lane);
  - `tx_core_clk` (`+TX_CORE_HALF`, mặc định 2,50025 ns, tức chậm 100 ppm như hai thạch anh thật);
  - mux pad, `+SRC=tx|gen`. Mux lái hai bản pad cùng giá trị, đều bằng `assign` nên đều strong:
    - một bản vào `xrx`;
    - một bản mang đúng tên `clk_p/clk_n/d_p/d_n` của TN1, vào `IBUFDS_DPHY` của RX mình và `afe_model`. Nhờ vậy
      khối copy từ TN1 giữ nguyên văn;
  - `ppi_tx_drv`, `pad_truth`;
  - `+GAP_NS`, `+TX_CORRUPT`;
  - `+NEG_FRONT=1`: phép thử âm của front check. Trong HS (theo `pad_truth`), bản pad của RX mình mang strength
    pull, giống `neg_front.sh` của TN1; bản của `xrx` vẫn strong.
- **Ở `+SRC=gen`:** TX bị giữ reset; generator ghi truth riêng vào `truth_gen.txt`.
- **Trình tự một run:**
  1. reset;
  2. chờ `init_done` của TX, của RX AMD và của RX mình;
  3. bật monitor;
  4. khởi động clock;
  5. phát các burst;
  6. chờ xả (như TN1);
  7. in kết quả.
- **Dòng kết quả:** giữ đúng format của TN1 cho `TB DONE`, `TB FRONT END CHECK`, `AFE`, `TB FTEL CFG`. Thêm
  `TB TX` (số burst giải được, mismatch, burst thừa, burst thiếu, khác line state) và `TB TXTIMING`.

**`run_exp2.sh`** (dựa trên `run_exp1.sh`):
- **Lệnh:** `build`, `run`, `E2a-0`…`E2a-5`, `model` (bộ `M_*`), `neg`, `summary`, `recheck`, `txtiming`
  (bảng timing TX theo rate), `evidence`.
- **Build:** hash nguồn gồm RTL, ba khối của `exp1/` và `exp2/*.sv`.
- **Mỗi run:**
  - tham số cấu hình lấy từ `exp1/cfg_for_rate.py`;
  - `csi2_dump.py bursts --max-trailer=-,<tmax>`, với `tmax` copy từ `run_exp1.sh` (HAS Table 4-7, không nhiễu);
  - ghi thêm `tbcheck.txt`, gồm các check mức TB. Với run `+SRC=gen`, phần này có cả phép so `truth.txt` với
    `truth_gen.txt`, bằng `tn2a_evidence.py padtruth <run>`.
- **Kết luận:** một run chỉ PASS khi cả `check.txt` lẫn `tbcheck.txt` PASS. `summary` in cả hai.
- **Output:** `fpga/work/exp2/` (git đã bỏ qua `work/`).

**`tn2a_evidence.py`:**
- Import `exp1/tn1_evidence.py` để dùng lại `read_truth`, `decode`, `decode_selftest`. File `exp1/` không bị sửa.
- Các check:

  | Check | Nội dung |
  |---|---|
  | `checker` | `csi2_dump.py selftest` PASS |
  | `decode` | giải mã lại mọi capture bằng code riêng, kết quả trùng `check.txt` |
  | `runs` | mọi run có `TB DONE OK`; truth đủ dòng; 0 burst thừa hoặc thiếu |
  | `tx` | 0 mismatch, trừ đúng một mismatch đã cài trong NEG-tx |
  | `padtruth` | ở E2a-0, `truth.txt` trùng `truth_gen.txt` từng byte, t0/t1 lệch ≤ 1 ps. Có selftest với một byte và một t0 bị sửa |
  | `front` | như TN1 |
  | `afe` | như TN1 |
  | `config` | như TN1 |
  | `sources` | như TN1 |
  | `copy` | các khối copy trong `tb_exp2a.sv` (front end của RX mình, front check, instance `m_ftel_dphy_rx_wrap`) vẫn trùng nguyên văn với `tb_exp1.sv`, để hai bench không lệch nhau |

### 3.3 Dùng lại, không sửa

- `exp1/`: `dphy_line_gen.sv`, `afe_model.sv` (đã có ghi chú cho TN2: đọc pad trễ 1 ps), `ppi_csv_mon.sv`,
  `cfg_for_rate.py`, `tn1_evidence.py` (import).
- `tools/csi2_dump.py`, mode `bursts`: truth cùng format, luật ghép theo thời gian dùng t0/t1 của `pad_truth`.
- RTL `logical/`, `config/`: không đụng. Nếu TN2a lộ lỗi RTL thì dừng, báo kèm bằng chứng; sửa RTL cần plan riêng.

## 4. Tiêu chí đạt (mỗi kịch bản)

- **`csi2_dump.py bursts`:** cả hai capture 0 lỗi.
  - RX AMD: trailer không giới hạn.
  - RX mình: trailer ≤ `tmax(rate)` của HAS Table 4-7 không nhiễu: 0 từ 600 Mb/s; 4 byte ở 260; 6 byte ở 400.
- **`tbcheck.txt`:**
  - `TB DONE OK`;
  - `TB TX`: 0 mismatch, 0 burst thừa, 0 burst thiếu, 0 khác line state;
  - front check: 0 khác trên hơn 0 lần so;
  - `AFE`: 0 lỗi line state, `term_en` không trễ và không thiếu.
- **E2a-0 thêm:** truth của `pad_truth` trùng truth của generator.
- **Chỉ báo cáo:** trailer của RX AMD, độ trễ, thời điểm `stopstate`, timing TX (có nhãn `OUTSIDE` nếu ra ngoài
  giới hạn).

## 5. Kịch bản

| ID | Rate, lane | Tham số | Mục đích |
|---|---|---|---|
| E2a-0a/b/c | 1440, 4 | `+SRC=gen`: độ dài của E1-1; góc của E1-3c (`+TRAIL=min +EXIT=min +LPX=min`); `+UNEVEN=1` | Chứng minh `pad_truth` bằng generator đã kiểm ở TN1. Hai RX phải PASS như TN1 |
| E2a-1 | 1440, 4 | burst 1–1024 byte, payload counter | Cơ bản. RX AMD phải PASS trước (chứng minh hookup TX và truth) |
| E2a-2a | 1440, 4 | `+PATTERN=prbs9 +REPEAT=2` | Như E1-2a |
| E2a-2b | 1440, 4 | `+PATTERN=synclike` | Như E1-2b |
| E2a-2c | 1440, 4 | `+UNEVEN=1` | Lane kết thúc lệch nhau 🔍 (`C_USE_LANE0_TXREADYHS`) |
| E2a-3 | 1440, 4 | `+GAP_NS=0 +LENS=1,4,64,256 +REPEAT=2` | Burst sát nhau: THS-EXIT nhỏ nhất của TX |
| E2a-4a | 260, 4 | timeout dài hơn | Rate thấp nhất; trailer của RX mình ≤ 4 |
| E2a-4b/c | 800 / 1500, 4 | | Phủ dải R1 |
| E2a-4d/e | 1440, 2 / 1 | | Số lane |
| E2a-5 | 260 400 600 800 1000 1200 1440 1500, 4 | `+TX_CORE_HALF=2.501` và `2.499` (±400 ppm), `+LENS=1,2,3,4,5,8,16,64,256 +REPEAT=6` | EoT với trail thật, LP-11 rơi vào mọi pha `core_clk` (16 run) |
| M_* | như trên | `+AFE=model` | Bộ phụ: RX mình sau `afe_model` |
| NEG-tx | 1440, 4 | `+TX_CORRUPT=1,3,0` | Check byte TX phải báo đúng 1 mismatch, và run phải FAIL |
| NEG-front | 1440, 4 | `+NEG_FRONT=1` | Front check phải đếm ra khác biệt |

**Khối lượng:**
- Khoảng 29 kịch bản, cộng 29 run `M_*` và 2 phép thử âm, tổng khoảng 60 run.
- 10 build: 8 rate × 4 lane, cộng 1440 × 2 lane và 1440 × 1 lane.

## 6. Kiểm chứng: vì sao sẽ tin được kết quả

| Lớp (như TN1 README §7) | TN2a |
|---|---|
| 1. Tín hiệu vào có đúng không | TX là IP của AMD. Byte trên pad được so với byte PPI ở mọi burst. `pad_truth` được kiểm bằng generator của TN1 (E2a-0) |
| 2. Bộ kiểm có biết báo FAIL không | Selftest của `csi2_dump.py`; NEG-tx; NEG-front; selftest của check `padtruth` |
| 3. PASS có tính đúng không | `tn2a_evidence.py decode`: giải mã độc lập, kết quả phải trùng `check.txt` |
| 4. Thứ được test là thứ trong repo | Check `sources` (hash nguồn); check `copy` (phần RX copy không lệch TN1) |
| 5. EoT không đạt nhờ may | E2a-5: TX lệch ±400 ppm, LP-11 rơi vào mọi pha `core_clk` |
| 6. Cùng front end | Front check ở mọi run hai RX, cộng NEG-front |

Cuối cùng chạy `run_exp2.sh recheck`: kiểm lại mọi output với `csi2_dump.py` hiện tại, không mô phỏng.

## 7. Các bước, cổng dừng, ước lượng ⚠️

| Bước | Việc | Cổng: nếu sai thì dừng và báo bạn | Ước lượng |
|---|---|---|---|
| 1 | Lưu plan thành `fpga/PLAN_TN2A.md`; thêm ghi chú ngày vào đầu `PLAN_TN1_TN3.md` (TN2 làm ở repo này; đường dẫn cũ `hw/rtl/ip/ftel_dphy_rx/x` ứng với `22fdx/rx/digital/x`) | — | 0,1 ngày |
| 2 = S0 | `exp2.tcl`, `ppi_tx_drv.sv`, `tb_exp2a.sv` bản đầu (chưa có `pad_truth`). Build 1440×4 (`EXP2_DEBUG=typical`). Chạy thử `+LENS=1,2,3 +TXLOG=1`, lần với `+TX_CORE_HALF=2.5` và lần với 2.50025 | (a) clock lane vào HS một lần và chạy liên tục; (b) burst 1 byte được; (c) pad chỉ 0/1; (d) TX khởi động trước khi hết timeout, ghi lại thời gian; (e) PLL của TX chạy được với clock lệch ppm; (f) front check 0 khác; (g) đo tốc độ mô phỏng | 0,5 ngày |
| 3 = S1 | `pad_truth.sv`; E2a-0a/b/c; NEG-tx | Truth trùng 100 % (t0/t1 lệch ≤ 1 ps); NEG-tx báo đúng 1 lỗi | 0,5 ngày |
| 4 = S2 | `run_exp2.sh` đủ lệnh; E2a-1 rồi E2a-2…4; thêm 5 build (260, 800, 1500, 1440×2, 1440×1) | RX AMD PASS E2a-1. Nếu chỉ RX mình hỏng: dừng, báo phát hiện RTL kèm bằng chứng | 0,5 ngày |
| 5 = S3 | 4 build còn lại (400, 600, 1000, 1200); E2a-5; bộ `M_*`; NEG-front; `tn2a_evidence.py`; bảng `txtiming` | Evidence PASS mọi check | 0,5 ngày |
| 6 = S4 | `exp2/README.md` (ghi chép nội bộ: sơ đồ, khối, kết quả, kiểm chứng, giới hạn); trạng thái và lệnh trong `fpga/README.md`; mục Kết quả ở cuối `PLAN_TN2A.md` | — | 0,25 ngày |

- **Tổng:** khoảng 2–2,5 ngày ⚠️. Plan cũ ước 1–2 ngày; phần tăng thêm là bộ giải mã pad và phần kiểm chứng.
- **Thời gian máy:**
  - mỗi build khoảng 6–8 phút ⚠️;
  - mỗi run khoảng 1–1,5 phút, vì TX khởi động khoảng 0,4 ms mô phỏng; S0 đo lại;
  - toàn bộ khoảng 1,5 giờ máy, chạy 2–3 luồng song song.
- **Bước dài:** mỗi bước dài tôi báo trước thời gian rồi chạy nền. Trước mỗi pha song song tôi kiểm RAM trống
  (máy dùng chung); dưới 15 GB thì chỉ chạy 2 luồng.

## 8. File

| File | Việc |
|---|---|
| `fpga/PLAN_TN2A.md` | Mới: bản plan này |
| `fpga/exp2/exp2.tcl`, `tb_exp2a.sv`, `ppi_tx_drv.sv`, `pad_truth.sv`, `run_exp2.sh`, `tn2a_evidence.py` | Mới. Có header FTEL như các file của `exp1/` |
| `fpga/exp2/README.md` | Mới: ghi chép kỹ thuật nội bộ, tiếng Việt |
| `fpga/README.md` | Sửa: trạng thái, cây thư mục, các lệnh của TN2a |
| `fpga/PLAN_TN1_TN3.md` | Sửa: chỉ thêm ghi chú ngày ở đầu file |
| `fpga/work/exp2/` | Output (git bỏ qua) |

- **Không đụng:** `logical/`, `config/`, `exp1/*`, `tools/*`, `probe/*`.
- **Repo public:**
  - chỉ nêu AMD/Xilinx, không nêu tên board hay vendor;
  - trước khi commit, quét danh sách token của nhóm trên các file mới;
  - commit chỉ khi bạn bảo.

## 9. Rủi ro

1. **TX khởi động lâu** (example: 384 µs) làm mỗi run dài. Cách giảm: chạy song song; S0 đo lại. `C_INIT` đã ở mức
   nhỏ nhất.
2. **Continuous clock hoặc `cl_txclkactivehs` không như kỳ vọng:** cổng S0. Phương án thay: chờ `cl_stopstate`.
3. **Lane kết thúc lệch nhau** khi `C_USE_LANE0_TXREADYHS` = true. Nếu TX không cho, thử một build với false; nếu
   vẫn không được thì ghi là giới hạn của TX và báo bạn.
4. **PLL của TX trong XSIM không chịu clock lệch ppm:** thay bằng cho `core_clk` của RX lệch (`+CORE_HALF`, như
   TN1), TX chạy đúng 200 MHz.
5. **Hai IP `mipi_dphy` trong một project:** example đã làm vậy và chạy được ✅.
6. **RX mình hỏng mà RX AMD đạt, truth đã được kiểm:** đó là phát hiện RTL. Dừng, báo kèm bằng chứng, sửa theo
   plan riêng, như TN1.
7. **Code copy từ `tb_exp1.sv` lệch dần theo thời gian:** check `copy` bắt được.

## 10. TN2a không kiểm

- Skew giữa lane và pha clock: TN1 đã phủ ±0,2 UI, còn TX trong mô phỏng không có skew.
- Góc timing của TX: IP không cho chỉnh.
- ULPS, escape mode, deskew, non-continuous clock.
- Packet CSI-2: thuộc TN2b.
- Hiệu ứng analog.
- 80 Mb/s (TX thấp nhất 260 Mb/s) và các rate ngoài R1.

## 11. Sau TN2a (chưa thuộc plan này)

- **TN2b:** plan riêng, cần tra trước:
  - tham số của CSI-2 TX SS 2.2;
  - chuỗi thanh ghi theo driver;
  - bảng nối PPI, viết lại ở đây vì bảng gốc nằm trong plan prototype nội bộ, không có trong repo này;
  - dùng lại probe `csi2_rx_no_phy`.
- **TN2c:** để sau.
- **Bàn giao:** `TN2_DESCRIPTION.md` và `TN2_REPORT.md` viết sau khi xong 2a và 2b (D3).

## 12. Độ tin cậy

- **HIGH:**
  - dữ kiện về TX: tham số, cổng, dải rate, timing đo trong example, strength của buffer;
  - phần RX của TN1 dùng lại được nguyên vẹn.
- **MED:**
  - thời gian chạy và thời gian khởi động TX;
  - việc lane kết thúc lệch nhau và clock lệch ppm chạy được trong XSIM;
  - ước lượng ngày công.
- **Kỳ vọng kết quả:** MED-HIGH là RX mình đạt. Timing thật của TX đo được đều nằm trong dải TN1 đã phủ, trừ
  TCLK-PREPARE 88,5 ns (TN1 chỉ thử 66 ns), nhưng vẫn trong giới hạn D-PHY.

## 13. Phát hiện khi làm (2026-10-22)

1. **Lệch `core_clk` của TX không làm line lệch** (S0, cổng e).
   - Model mô phỏng khối clock của TX cho byte clock và pad đúng rate danh định, bất kể chu kỳ của `core_clk` mà TX
     nhận.
   - Bằng chứng: `S0_exact` (TX 200 MHz) và `S0_ppm` (chậm 100 ppm) có `xil_ppi.csv`, `ftel_ppi.csv` và
     `expected.txt` giống từng byte. Trong `tn2a.vcd`, bỏ riêng clock của TX ra, thì 430 178 lần đổi giá trị trùng
     tới từng ps, trong đó có 162 172 lần đổi ở pad.
   - Vì vậy E2a-5 dùng phương án của rủi ro 4: `core_clk` của hai RX lệch ±400 ppm (`+CORE_HALF=2.501` và `2.499`),
     giống E1-5, còn TX chạy đúng 200 MHz. `+TX_CORE_HALF` vẫn có trong bench, mặc định 2.5.
2. **TX khởi động lâu, và lâu khác nhau theo rate:**
   - `init_done` của TX lên sau 380–571 µs, dù `C_INIT` = 99 µs: 395,2 µs ở 260 Mb/s, 570,5 µs ở 800, 383,3 µs ở
     1440, 380,5 µs ở 1500 (bảng đủ 8 rate ở §14).
   - Clock lane được request 1 µs sau `init_done` (ở 1440 Mb/s là 384,26 µs) và chạy sau đó khoảng 0,5 µs.
   - Mỗi run vì vậy dài 400–600 µs mô phỏng, tức 85–100 s máy. Riêng các run `+SRC=gen` không chờ TX, nên chỉ mất
     12–13 s.
3. **Front check bị race ở t = 2 ps** (E2a-4d 1440×2 và E2a-4e 1440×1, 1 khác trên khoảng 31 000 lần so).
   - Diễn biến:
     - pad của TX rời X lên LP-11 ở 1 ps;
     - cả hai bộ `IBUFDS_DPHY` lên 11 ở 2 ps;
     - ở build có lane không dùng, wire của các lane đó bỏ trống, nên khối so bị kích ngay ở t = 0, và lần so đầu
       rơi đúng vào 2 ps.
   - Lần so đó thấy phía AMD chậm một delta. Mọi lần so sau đều trùng.
   - Ở build 4 lane, VCD của S0 cho thấy lần so đầu ở 4 ps, nên không có race.
   - Bằng chứng: `work/exp2/DBG-E2a-4d/tn2a.vcd`, build 1440×2 debug typical, tái hiện đúng 1/32 009.
   - Cách xử lý (bạn chọn 22/10, phương án 1):
     - bench TN2a in một dòng `TB FRONT END CHECK START` với số lần so tới 2,5 ps và số lần khác, rồi đặt lại bộ đếm
       (`p_fe_start`, nằm ngoài khối copy);
     - TN1 và khối copy giữ nguyên;
     - `tbcheck` báo `front` FAIL nếu thiếu dòng START.
4. **Chữ in bị đệm khoảng trắng:** toán tử `?:` giữa hai string literal đệm literal ngắn hơn. Các dòng mới của TN2a
   dùng `string'()`. Riêng `TB DONE      OK` giữ đúng format TN1.
5. **Lane kết thúc lệch nhau chạy được** với `C_USE_LANE0_TXREADYHS` = true (E2a-2c), nên rủi ro 3 không xảy ra.
   - Mọi `txreadyhs` của TX lên xuống cùng nhau (S0).
   - Driver tiến theo `txreadyhs` của chính lane đó. Với `+UNEVEN=1`, lane 0 là lane dài nhất.
6. **Check `sources` theo từng run:** `run_exp2.sh` ghi hash nguồn của build vào `args.txt` của mỗi run, và check so
   hash của từng run với nguồn hiện tại. TN1 chỉ so hash của build. Cách mới chặt hơn: run nào chạy trước lần sửa
   nguồn cuối cùng thì FAIL.
7. **NEG-front làm RX mình kẹt, và đó là tác dụng phụ của bench.**
   - Hiện tượng: RX mình 0/40 burst, `term_en` thiếu 36 lần; NEG-E1-1 của TN1 thì RX mình vẫn đạt.
   - Nguyên nhân:
     - model `IBUFDS_DPHY` tính strength trong `always @(*)`, và trong XSIM khối này không chạy lại khi chỉ strength
       đổi;
     - bench nhả pull 1 ps sau khi pad lên LP-11 (cờ HS của `pad_truth` đọc pad trễ 1 ps), lúc giá trị pad đã giữ
       nguyên;
     - vì vậy buffer của RX mình giữ LP 00 cho tới request kế, và RX mình không bao giờ thấy LP-11.
   - Bằng chứng: `work/exp2/DBG-NEG-front/tn2a.vcd`.
   - Đây không phải phát hiện RTL. NEG-front vẫn chứng minh điều nó cần chứng minh: front check đếm 25 744 / 32 674
     lần khác, và RX AMD vẫn đạt.
   - `tn2a_evidence.py` chỉ in kết quả của RX mình và của `afe` ở run này, không chấm.

## 14. Kết quả (2026-10-22)

**60/60 run ra đúng kỳ vọng. `tn2a_evidence.py evidence`: PASS (10/10 checks).** Chi tiết và bảng số nằm ở
[`exp2/README.md`](exp2/README.md) §6–§7.

- **Hai RX:**
  - 29/29 kịch bản PASS cho cả hai RX, ở 8 rate từ 260 tới 1500 Mb/s, với 1, 2 và 4 lane;
  - bộ phụ `M_*` (RX mình sau `afe_model`): 29/29 PASS;
  - không có phát hiện RTL. RTL `logical/` và `config/` không đổi.
- **E2a-5** (`core_clk` của hai RX lệch ±400 ppm): RX mình nhận 432/432 lane burst ở mỗi rate, với cả hai front end.
  Trailer bằng 0 từ 400 Mb/s; ở 260 Mb/s sau `afe_model` là 0–2 byte, trong giới hạn 4.
- **Trailer của RX AMD:** 2–19 byte tuỳ rate. RX mình sau `IBUFDS_DPHY`: 0 ở mọi rate.
- **Timing TX:** mọi tham số nằm trong giới hạn D-PHY v1.1 ở cả 8 rate (`run_exp2.sh txtiming`: 0 giá trị
  `OUTSIDE`). So với TN1, có hai điểm mới đã được phủ:
  - TCLK-PREPARE 81,9–88,5 ns (TN1 chỉ thử 66 ns);
  - THS-PREPARE 95,6–103,0 ns ở 260 Mb/s (giới hạn tới 108,1 ns).
- **Khởi động TX** (`init_done`, µs):

  | 260 | 400 | 600 | 800 | 1000 | 1200 | 1440 | 1500 |
  |---|---|---|---|---|---|---|---|
  | 395,2 | 570,5 | 386,2 | 570,5 | 392,9 | 386,2 | 383,3 | 380,5 |

- **`pad_truth`:** 160/160 lane burst trùng generator từng byte, t0/t1 lệch 0 ps (E2a-0 và `M_E2a-0`).
- **Phép thử âm:**
  - NEG-tx: đúng 1 mismatch ở chỗ đã cài, và hai RX vẫn khớp pad;
  - NEG-front: 25 744 / 32 674 lần so khác. RX mình kẹt (§13 mục 7).
- **Kiểm chính script kiểm chứng:**
  - `tn2a_evidence.py evselftest`: 1 ca sạch và 9 lỗi cài; mỗi lỗi làm hỏng đúng các check của nó;
  - `run_exp2.sh recheck`: 124 file, chỉ 1 file đổi (`DBG-E2a-4d`, run chạy trước khi thêm `p_fe_start`).
- **Thời gian:** 10 build (4 build mới) và 60 run xong trong 40 phút, chạy 3 tiến trình. Tổng thời gian mô phỏng là
  5 573 s.

**Khác với plan:**
- **E2a-5 lệch `core_clk` của RX** (`+CORE_HALF=2.501/2.499`), không lệch TX (`+TX_CORE_HALF`). Mặc định của
  `+TX_CORE_HALF` là 2,5 ns, không phải 2,50025 ns (§13 mục 1). §3.2, §5 và §7 vẫn ghi theo dự kiến ban đầu.
- Run của E2a-5 tên là `E2a-5_<rate>_slow` và `E2a-5_<rate>_fast`.
- Front check thêm `p_fe_start` (§13 mục 3, do bạn chọn). Check `sources` so theo từng run (§13 mục 6).
- Check `afe` không chấm NEG-front (§13 mục 7).
- Thêm lệnh `tn2a_evidence.py evselftest`, không có trong plan, để kiểm chính script kiểm chứng như §7.7 của README
  TN1, nhưng chạy tự động.
- Thêm hai run debug (`DBG-E2a-4d`, `DBG-NEG-front`) trên hai build debug typical (1440×4 và 1440×2), để đọc VCD. Các
  run này không thuộc tập kiểm.
- **Thời gian:**
  - Plan ước 2–2,5 ngày công; thực tế từ plan tới kết quả làm trong ngày 22/10.
  - Build mới mất khoảng 7 phút (3 phút Vivado, 4 phút compile); compile lại chỉ mất vài chục giây.
  - Run từ TX mất 85–130 s ở 4 lane, khoảng 55 s ở 1–2 lane, đúng như ước lượng.
