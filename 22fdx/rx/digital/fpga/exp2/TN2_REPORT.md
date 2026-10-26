# TN2 — Báo cáo thí nghiệm: TX của AMD phát vào `ftel_dphy_rx` và vào RX của AMD (mô phỏng XSIM)

> Báo cáo kết quả TN2 cho team FPGA. Cách dựng bench và cách chạy lại nằm ở
> [`TN2_DESCRIPTION.md`](TN2_DESCRIPTION.md).
> RTL `ftel_dphy_rx` theo HAS v0.16, là RTL của TN1, giống RTL trên nhánh `dev` của repo fu3_dphy từ commit `66f9f39`.
> - TN2a: chạy ngày 2026-10-22, 60 run. Kiểm lại ngày 2026-10-26, không mô phỏng lại, với bộ so có thêm hai luật timing
>   ở PPI: kết quả không đổi.
> - TN2b: chạy ngày 2026-10-23, 39 run. Chạy lại ngày 2026-10-26 với khối chỉnh `rxactivehs` thay cho testbench, thêm
>   kịch bản lỗi SoT sync E2b-9: 40 run.
>
> Phiên bản 1.0, ngày 2026-10-26. Nhóm D-PHY RX viết.

## 1. Tóm tắt

- **TN2a, TX D-PHY của AMD phát vào hai RX:**
  - 29/29 kịch bản PASS cho cả hai RX, ở 8 rate từ 260 tới 1500 Mb/s, với 1, 2 và 4 lane. Bộ chạy phụ, với RX mình sau
    mô hình AFE, cũng đạt 29/29. Hai phép thử âm hỏng đúng chỗ đã cài.
  - Không tìm thấy lỗi nào ở `ftel_dphy_rx`.
  - Timing của TX đo trên pad nằm trong giới hạn D-PHY v1.1 ở cả 8 rate. Hai giá trị vượt dải TN1 đã thử: TCLK-PREPARE
    82–89 ns, và THS-PREPARE ở 260 Mb/s 96–103 ns. RX mình vẫn đạt với cả hai.
  - Với `core_clk` của hai RX lệch ±400 ppm so với TX, RX mình nhận đủ 432/432 lane burst ở mỗi rate, trailer trong
    giới hạn của HAS.
- **TN2b, frame RAW10 qua CSI-2 TX Subsystem vào hai đường nhận CSI-2:**
  - R-X, đường nhận của AMD có D-PHY, ra đúng từng pixel ở mọi run.
  - **Phát hiện:** nối thẳng `ftel_dphy_rx` vào CSI-2 RX Subsystem không PHY thì controller của AMD không nhận packet
    nào, dù PPI mang đúng các packet đó. `ftel_dphy_rx` nâng `rxactivehs` trước `rxsynchs` vài byte clock, như HAS cho
    phép. D-PHY của AMD nâng hai tín hiệu cùng lúc, và controller của AMD cần `rxactivehs` không lên trước `rxsynchs`
    (§4.1). Đây không phải lỗi so với HAS, mà là chỗ PPI của `ftel_dphy_rx` khác PPI mà controller của AMD chờ.
  - **Cách xử lý, chỉ ở FPGA:** khối `m_ftel_ppi_act_gate` giữ `rxactivehs` của mỗi lane ở 0 tới `rxsynchs`. Khối có 6
    flip-flop với 4 lane và không thêm trễ. RTL ASIC không đổi (§4.2).
  - Qua khối này, R-F ra đúng từng pixel ở 27/27 run: 14 kịch bản ở 4 rate, 2 và 1 lane active, ±400 ppm, RX cấu hình
    muộn, tắt rồi bật lại luồng, cộng 13 run với RX mình sau mô hình AFE. Chuỗi packet và thanh ghi của R-F bằng R-X.
    Ba phép thử âm hỏng đúng chỗ (§4.3).
  - **Lỗi SoT sync ở một lane (E2b-9):** controller không treo, và các frame sau đúng từng pixel. Frame có lỗi mất hai
    line, và một line sai vẫn ra `video_out`; chỉ ISR có cờ CRC (§4.5).
- **Kiểm chứng:** script kiểm chứng riêng của mỗi bench đạt mọi check (TN2a 10/10, TN2b 12/12). Tự thử của chúng bắt
  đủ các lỗi cài sẵn, kể cả ba lỗi giống các lỗi tester team FPGA đã cài vào capture của TN1 (§5).
- **Giới hạn chính:** TX, RX AMD, ba subsystem và front end đều là model mô phỏng của AMD. Kết luận cho board còn cần
  TN3.

## 2. Thí nghiệm

```
TN2a
  TX AMD (mipi_dphy 4.3 MASTER) ─► pad ─┬─► RX AMD (mipi_dphy 4.3 SLAVE) ─► PPI ─► xil_ppi.csv ──┐
                                        ├─► IBUFDS_DPHY ─► ftel_dphy_rx ─► PPI ─► ftel_ppi.csv ──┴─► so với truth.txt
                                        └─► pad_truth ─► truth.txt (byte giải từ pad)

TN2b
  frame RAW10 ─► CSI-2 TX Subsystem ─► pad ─┬─► R-X: CSI-2 RX Subsystem có D-PHY ─► video_out ────────┐
                                            └─► R-F: IBUFDS_DPHY ─► ftel_dphy_rx ─► khối chỉnh        ├─► so với golden
                                                     ─► CSI-2 RX Subsystem không PHY ─► video_out ────┘
```

- **TN2a:** TX D-PHY của AMD, điều khiển ở PPI, phát burst vào RX D-PHY của AMD và vào RX mình. Bên nhận và bộ so như
  TN1. Truth được giải từ pad, độc lập với hai RX.
- **TN2b:** CSI-2 TX Subsystem của AMD phát frame RAW10 tổng hợp. R-X là CSI-2 RX Subsystem có D-PHY. R-F là đường của
  prototype: RX mình, khối chỉnh `rxactivehs`, rồi CSI-2 RX Subsystem không PHY. `video_out` của hai RX được so từng
  pixel với golden; packet trên ba PPI và thanh ghi của ba subsystem cũng được so.
- Ở cả hai bench, RX mình đứng sau đúng buffer `IBUFDS_DPHY` mà IP AMD dùng, và bench kiểm ở mọi run rằng đầu ra LP
  của hai bộ buffer trùng nhau.

Chi tiết bench, luật so và danh sách kịch bản nằm ở [`TN2_DESCRIPTION.md`](TN2_DESCRIPTION.md) §4–§7.

## 3. Kết quả TN2a

### 3.1 Payload

- 29/29 kịch bản PASS cho cả hai RX; bộ phụ `M_*`, với RX mình sau `afe_model`, cũng 29/29. Ví dụ ở E2a-1, mỗi RX đúng
  40/40 lane burst.
- Đúng ở 8 rate từ 260 tới 1500 Mb/s, ở 1, 2 và 4 lane, với lane kết thúc lệch nhau, payload giống sync, PRBS-9 và
  burst sát nhau (THS-EXIT 137,6 ns).
- Byte trên pad bằng byte đã giao cho TX ở mọi burst của 54 run từ TX. Phép so này dùng bộ giải mã pad, độc lập với
  hai RX.
- Bộ giải mã pad được kiểm bằng line generator của TN1: ở E2a-0 và `M_E2a-0`, 160 lane burst trùng từng byte với truth
  của generator, t0 và t1 lệch đúng 0 ps.

### 3.2 Trailer và độ trễ

Trailer là số byte thừa mỗi burst; sau `afe_model`, số trong ngoặc là số burst có trailer trên tổng số. Độ trễ là của
byte payload cuối, từ lúc nó rời pad tới lúc ra PPI.

| Rate (Mb/s) | Kịch bản | Trailer: AMD | Trailer: RX mình sau `IBUFDS_DPHY` | Trailer: RX mình sau `afe_model` | Giới hạn của RX mình | Độ trễ: AMD | Độ trễ: RX mình |
|---|---|---|---|---|---|---|---|
| 260 | E2a-4a, E2a-5 | 2 | 0 | 0–2 (20/40 ở E2a-4a; 216/432 ở E2a-5) | 4 | 167 ns | 1117 ns |
| 400 | E2a-5 | 4 | 0 | 0 | 6 | 99 ns | 741 ns |
| 600 | E2a-5 | 7 | 0 | 0 | 0 | 66 ns | 484 ns |
| 800 | E2a-4b, E2a-5 | 9–10 | 0 | 0 | 0 | 50 ns | 363–366 ns |
| 1000 | E2a-5 | 12–13 | 0 | 0 | 0 | 40 ns | 295 ns |
| 1200 | E2a-5 | 15 | 0 | 0 | 0 | 33 ns | 244 ns |
| 1440 | E2a-1 tới E2a-3, E2a-4d, E2a-4e, E2a-5 | 17–18 | 0 | 0 | 0 | 28 ns | 202–205 ns |
| 1500 | E2a-4c, E2a-5 | 18–19 | 0 | 0 | 0 | 26 ns | 195–198 ns |
| 1440, line generator | E2a-0a, E2a-0b, E2a-0c | 14–17 | 0 | 0 | 0 | 28–32 ns | 201–206 ns |

### 3.3 Timing của TX trên pad

Min..max trên mọi run từ TX ở rate đó, tính bằng ns. Bảng đủ, kèm giới hạn của D-PHY v1.1 ở từng rate, in bằng
`run_exp2.sh txtiming`. **Không giá trị nào ra ngoài giới hạn.**

| Tham số | 260 | 400 | 600 | 800 | 1000 | 1200 | 1440 | 1500 | TN1 đã thử ở 1440 |
|---|---|---|---|---|---|---|---|---|---|
| TLPX (data, clock) | 55,0 | 55,0 | 55,0 | 55,0 | 55,0 | 55,0 | 55,0 | 55,0 | 50 / 75 |
| THS-PREPARE | 95,6–103,0 | 87,3 | 86,6–89,9 | 77,3 | 77,9–81,9 | 79,9–83,2 | 76,3–81,3 | 75,9–80,9 | 42,8 / 66 / 89,2 |
| THS-PREPARE + THS-ZERO | 300,9–305,5 | 274,4 | 264,6–268,0 | 223,2 | 210,6–214,6 | 223,8–227,1 | 212,9–217,9 | 207,1–212,1 | 151,9 / 182 |
| THS-TRAIL | 85,9 | 82,9 | 81,9 | 84,2 | 83,3 | 82,7 | 80,1 | 76,9 | 62,8 / 75,3 / 107,8 |
| THS-EXIT | 322,8–327,4 | 307,7 | 301,8–305,1 | 287,7 | 287,1–291,1 | 285,1–291,8 | 137,6–290,4 | 285,1–291,8 | 100 / 150 |
| TCLK-PREPARE | 86,8 | 87,3 | 88,2 | 87,3 | 81,9 | 86,6 | 88,5 | 88,2 | 66 |
| TCLK-PREPARE + TCLK-ZERO | 379,8 | 375,7 | 347,1 | 363,8 | 343,1 | 377,6 | 375,5 | 358,4 | 360 |

- THS-EXIT phụ thuộc thời gian bench chờ sau `stopstate` (`+GAP_NS`). Giá trị 137,6 ns là của E2a-3, khi burst kế được
  request ngay; các run khác chờ 150 ns.
- TCLK-PRE khoảng 2,05–2,18 µs, vì bench chờ 2 µs sau khi clock chạy rồi mới phát burst đầu.
- THS-TRAIL không đổi trong một rate, vì TX không có jitter trail và không có nhiễu.
- Hai chỗ TN1 chưa thử nay đã được TX thật phủ, và RX mình đạt: TCLK-PREPARE 81,9–88,5 ns (TN1 chỉ thử 66 ns), và
  THS-PREPARE ở 260 Mb/s 95,6–103,0 ns, gần mức max 108,1 ns (TN1 thử giá trị giữa khoảng ở rate này).

**Khởi động TX** (`C_INIT` = 99 µs):

| Rate (Mb/s) | 260 | 400 | 600 | 800 | 1000 | 1200 | 1440 | 1500 |
|---|---|---|---|---|---|---|---|---|
| `init_done` của TX (µs) | 395,2 | 570,5 | 386,2 | 570,5 | 392,9 | 386,2 | 383,3 | 380,5 |

### 3.4 Cuối burst ở mọi pha của `core_clk` (E2a-5)

- Model clock của TX cho line đúng rate danh định, bất kể chu kỳ `core_clk` của TX: lệch 100 ppm ở phía TX cho pad trùng
  tới từng ps. Vì vậy E2a-5 lệch `core_clk` của hai RX ±400 ppm, như E1-5 của TN1. Điều RX cần là pha tương đối giữa
  LP-11 và `core_clk`, nên hai cách tương đương.
- Mỗi rate có 432 lane burst cho mỗi RX và mỗi front end, với LP-11 rơi vào mọi pha của `core_clk`.
- **Kết quả:** ở cả 8 rate, RX mình nhận đủ 432/432 lane burst ở cả hai front end. Trailer bằng 0 từ 400 Mb/s; ở
  260 Mb/s là 0–2 byte sau `afe_model`, dưới giới hạn 4.
- **Giới hạn:** trail của TX không đổi trong một rate, nên E2a-5 phủ mọi pha nhưng không phủ các độ dài trail khác
  nhau. Các độ dài trail (min, mặc định, max, jitter, nhiễu) đã được E1-5 của TN1 phủ.

### 3.5 Timing ở PPI (kiểm lại ngày 2026-10-26)

Với hai luật timing ở PPI mới ([`TN2_DESCRIPTION.md`](TN2_DESCRIPTION.md) §6.1), 60/60 run giữ nguyên kết quả:
- ở mọi lane burst, `rxsynchs` High đúng một mẫu: cùng chu kỳ với byte payload đầu ở RX mình, trước byte đầu một chu kỳ
  ở RX AMD;
- lệch giữa các lane bằng 0 byte clock ở mọi run có nhiều lane. TX trong mô phỏng không có skew giữa lane.

Riêng NEG-front không có số đo của RX mình, vì PPI của RX mình ở đó hỏng có chủ ý.

### 3.6 Đọc kết quả TN2a

- **Payload:** khi TX thật phát vào, phần digital của RX mình nhận đúng mọi payload như RX AMD, ở mọi rate và mọi số
  lane.
- **Trailer:**
  - RX AMD giữ 2–19 byte tuỳ rate. RX mình sau `IBUFDS_DPHY` cắt hết ở mọi rate. Sau `afe_model` cũng cắt hết, trừ
    260 Mb/s (0–2 byte, dưới giới hạn 4).
  - Ở 1440 Mb/s, RX AMD giữ 17–18 byte với TX, so với 14–17 byte với line generator. Lý do: trail của TX (80,1 ns) dài
    hơn trail mặc định của generator (75,3 ns) khoảng một byte time (5,56 ns).
- **Độ trễ:** RX mình trễ hơn RX AMD 6,7–7,5 lần, như TN1, do delay line 32 byte cần cho việc cắt trailer.

## 4. Kết quả TN2b

### 4.1 Phát hiện: controller của AMD không nhận PPI của `ftel_dphy_rx` khi nối thẳng

**Hiện tượng**, ở 5 run không có khối chỉnh, cả 4 rate (E2b-1, E2b-4a, E2b-4b, E2b-4c, E2b-6):
- R-X đúng từng pixel;
- PPI vào R-F mang đúng chuỗi packet của R-X (ví dụ 35/35 packet ở E2b-1), không lỗi ECC hay CRC;
- nhưng R-F ra 0 line, packet count của R-F bằng 0, ISR không có frame received và không có cờ lỗi nào.

**Đầu mỗi burst, đo trên capture**, tính bằng byte clock. Mỗi run có 140 lane burst (35 packet × 4 lane; E2b-6: 284), và
giá trị đúng như bảng ở mọi lane burst.

| Rate (Mb/s) | Run | `ftel_dphy_rx`: `rxactivehs` → `rxsynchs` | `ftel_dphy_rx`: `rxsynchs` → byte đầu | D-PHY AMD: `rxactivehs` → `rxsynchs` | D-PHY AMD: `rxsynchs` → byte đầu |
|---|---|---|---|---|---|
| 260 | E2b-4a | 7 | 0 | 0 | 1 |
| 800 | E2b-4b | 12 | 0 | 0 | 1 |
| 1440 | E2b-1, E2b-6 | 19–20 | 0 | 0 | 1 |
| 1500 | E2b-4c | 19–20 | 0 | 0 | 1 |

**Chẩn đoán** ở 1440 Mb/s: testbench sửa đầu burst của PPI vào R-F theo từng cách.

| Run | Thay đổi trên PPI vào R-F | `rxactivehs` → `rxsynchs` | R-F |
|---|---|---|---|
| `DBG-E2b-1-xfill` | bit X của `rxdatahs` (khi `rxvalidhs` = 0) thành 0 | 19–20 | 0 line |
| `DBG-E2b-1-amd1` | như D-PHY AMD: `rxsynchs` trước byte đầu, `rxactivehs` từ `rxsynchs` | 0 | PASS |
| `DBG-E2b-1-amd2` | chỉ dời `rxsynchs` lên trước byte đầu; `rxactivehs` vẫn sớm | 19–20 | 0 line |
| `DBG-E2b-1-amd3` | chỉ giữ `rxactivehs` tới `rxsynchs`; `rxsynchs` vẫn cùng byte đầu | 0 | PASS |

**Kết luận:** controller CSI-2 của AMD (RX Subsystem không PHY) cần `rxactivehs` không lên trước `rxsynchs`. Vị trí của
`rxsynchs`, cùng chu kỳ với byte đầu như HAS yêu cầu, không phải vấn đề.

**Vì sao không sửa RTL:**
- HAS cho phép `rxactivehs` lên cùng lúc hoặc trước `rxsynchs` (HAS §5.1).
- Các yêu cầu của controller CSI-2 RX trong chip đối với PPI (HAS, bảng A-2) dựa vào điều đó: sau một lỗi SoT sync,
  `rxactivehs` giữ tới hết burst dù không có `rxsynchs`.
- Vậy RTL đúng theo HAS. Chỗ khác nhau là giữa hợp đồng PPI đó và controller của AMD dùng ở prototype, nên cách xử lý
  nằm ở FPGA.

### 4.2 Khối chỉnh `rxactivehs`

[`fpga/rtl/m_ftel_ppi_act_gate.sv`](../rtl/m_ftel_ppi_act_gate.sv), chỉ dùng ở FPGA. Ở mỗi lane, `rxactivehs` ra lên
cùng `rxsynchs` đầu tiên của burst và giữ tới hết burst. Burst không có `rxsynchs` thì giữ ở 0. Không thêm trễ; mọi tín
hiệu PPI khác đi thẳng. Port và cách nối ở [`TN2_DESCRIPTION.md`](TN2_DESCRIPTION.md) §5.3.

**Kiểm riêng** (`fpga/rtl/run_rtl.sh all`, 2026-10-26):
- Lint VCS với 1, 2 và 4 lane: 0 error, 0 warning, 0 lint. Kiểm luật viết RTL: 0 vi phạm.
- Unit testbench VCS, với model riêng, burst ngẫu nhiên và burst có hướng:

  | Số lane | Số lần so với model | Khác | Burst |
  |---|---|---|---|
  | 1 | 926 755 | 0 | 3 008 |
  | 2 | 924 855 | 0 | 6 007 |
  | 4 | 935 860 | 0 | 12 005 |

  Mọi trường hợp đều có mặt. Ở 4 lane: `rxsynchs` cùng byte đầu 1 578 lần, muộn hơn 6 208, không có `rxsynchs` 4 160;
  burst sau đúng một chu kỳ nghỉ 1 183; `rxsynchs` rộng hơn một chu kỳ 781; reset giữa burst 18; byte clock dừng giữa
  burst 24. Một bản sửa hỏng của khối làm testbench báo FAIL.
- Vivado 2025.2, synth out-of-context trên part của board, 4 lane, byte clock 224 MHz (tức 1792 Mb/s, mức trần thiết
  kế của `ftel_dphy_rx`):
  - 6 flip-flop, 6 LUT; WNS +1,089 ns, WHS +0,018 ns;
  - `report_methodology`: 13 cảnh báo, 0 critical warning. Một cảnh báo là thiếu hoạt động RAM cho ước lượng công suất
    (AVAL-344); 12 cảnh báo là delay min bằng max ở port (XDCH-2), do ràng buộc out-of-context;
  - `report_cdc`: chỉ có đường reset, đã đặt false path, và 2 flip-flop đồng bộ reset có `ASYNC_REG`.

**Trong TN2b:** ở 31 run `SH_*`, khối trùng model của testbench ở 436 865 byte clock, 0 khác.

### 4.3 Kết quả qua khối chỉnh

Ngày 2026-10-23, testbench giữ `rxactivehs` vào R-F tới `rxsynchs` theo đúng luật của khối (cờ chẩn đoán
`+PPI_AMD_TIMING=3`). Ngày 2026-10-26, khối chỉnh thay testbench, và toàn bộ TN2b chạy lại.

- **27/27 run PASS cho cả hai đường nhận:** 14 kịch bản (E2b-1 tới E2b-8) và 13 run `M_*`. Đúng từng pixel, đúng số
  line, mỗi frame một SOF, ở 4 rate 260, 800, 1440 và 1500 Mb/s, với 4, 2 và 1 lane active, ±400 ppm, RX cấu hình muộn,
  tắt rồi bật lại luồng, sau cả `IBUFDS_DPHY` lẫn `afe_model`.
- **Controller thấy hai PHY như nhau:** R-F nhận cùng chuỗi packet với R-X (VC, data type, word count, payload) ở mọi
  run, cùng packet count, cùng image info, cùng cờ lỗi.
- **Ba phép thử âm hỏng đúng chỗ đã cài:**
  - NEG-ecc: bit cài rơi vào header và được sửa; chỉ R-F báo lỗi ECC 1 bit; mọi pixel vẫn đúng;
  - NEG-crc: R-F có đúng một pixel sai, đúng pixel chứa bit cài (frame 0, line 0, pixel 4: 0x024 thay cho 0x004); chỉ
    R-F báo CRC;
  - NEG-front: check front end đếm 356 598 khác biệt trong 370 519 lần đổi, trong khi R-X vẫn đạt.
- **So với lần chạy 2026-10-23,** khi testbench giữ `rxactivehs`: mọi CSV và `frames.txt` của 39 run trùng từng byte
  (282/282 file), và `check.txt` trùng 39/39. Vậy khối cho đúng thứ testbench đã cho, ở mọi burst.

### 4.4 Thanh ghi và thứ tự cấu hình

- **TX:** ISR = 0 ở mọi run.
- **R-X và R-F:** frame received, không cờ lỗi, và R-F có packet count và image info của VC0 bằng R-X, ở mọi run được
  chấm (24 run). Bốn run chỉ báo cáo: E2b-6, `M_E2b-6`, E2b-8 (frame đầu bị cắt hoặc thiếu FE, cả hai RX báo frame sync
  error của VC0) và E2b-9 (§4.5).
- **Bit 27:24 trong ISR của R-F đọc ra X** ở 37/40 run, tức mọi run mà R-F được cấu hình khi `ftel_dphy_rx` chưa có byte
  clock. Ở ba run E2b-6, R-F được cấu hình khi byte clock đã chạy, và các bit này đọc ra 0.
  - Driver của AMD không định nghĩa bit 27:23; mặt nạ ngắt của driver là 0xF07FFFFF.
  - Lý do: byte clock của `ftel_dphy_rx` dừng khi clock lane không ở HS, nên phần chạy theo byte clock trong controller
    không có cạnh clock lúc reset. R-X không gặp, vì D-PHY của AMD có byte clock ngay từ lúc khởi động.
- **Byte clock chưa chạy lúc cấu hình:** R-F vẫn qua vòng chờ reset của driver ("soft reset done" sau 1,1 µs), và nhận
  đúng sau đó.
- **Thứ tự cấu hình:**
  - cấu hình RX trước khi TX chạy, như example camera của AMD, chạy cho cả hai RX;
  - cấu hình RX giữa frame 0 (E2b-6) cũng chạy: từ SOF kế tiếp, cả hai RX ra đúng frame. Packet count khác nhau một
    chút (R-X 59, R-F 60), vì hai RX bắt đầu ở hai chỗ khác nhau của frame 0;
  - **đề xuất cho TN3:** theo thứ tự của AMD, che ISR bằng mặt nạ của driver. Nếu muốn các bit dự trữ sạch, cấu hình
    (hoặc soft reset) R-F sau khi clock lane vào HS.
- **Tắt rồi bật lại luồng (E2b-8):** testbench tắt TX (`CCR` = 0) ngay khi hai RX nhận xong frame 0, chờ 20 µs rồi bật
  lại.
  - Clock lane rời HS, và byte clock của cả hai RX dừng từ 413,2 µs tới khoảng 797 µs.
  - TX nhận frame 1 vào line buffer ngay sau khi bật lại (SOF ở 437,2 µs), nhưng tới 797,0 µs mới phát FS của frame đó.
    `CCR[2]` không lên lại trong 200 lần đọc.
  - R-F vẫn ra đúng cả 4 frame.

### 4.5 Lỗi SoT sync ở một lane (E2b-9)

Ở lane 0, packet 5 (line 4 của frame 0), testbench bỏ `rxsynchs` và `rxvalidhs` của burst đó và đặt `errsotsynchs` vào
chu kỳ của `rxsynchs`. Đó là PPI của `ftel_dphy_rx` sau một lỗi SoT sync, theo HAS (bảng A-2). Khối chỉnh giữ
`rxactivehs` của burst đó ở 0. 1440 Mb/s, 3 frame.

| | Kết quả |
|---|---|
| PPI vào R-F | Lane 0 có 52 burst, lane 1–3 có 53. `errsotsynchs` lên một lần, trong packet 5 của các lane khác, lúc `rxactivehs` của lane 0 bằng 0 |
| R-X | 48/48 line đúng, ISR sạch |
| R-F, frame 1 và 2 | Trùng golden từng pixel, đúng word count ở mọi line: **controller phục hồi**, không treo |
| R-F, frame 0 | 15 line thay vì 16: 14 line đúng (line 0–3 và 6–15); không có line 4 và 5; thay vào đó là 1 line lẫn. Trong line lẫn, byte của lane 0 là của line 5. Ở lane 1–3, 17 byte đầu là của line 4, phần sau là byte 3 tới 185 của line 5 |
| ISR của R-F | Frame received, frame level của VC0 (bit 0), CRC (bit 9). Không có bit SoT sync (bit 12), dù PPI có `errsotsynchs`. Packet count: R-F 47, R-X 48 |

- **Cái giá của một lỗi sync ở một lane là hai line,** và một trong hai line là line sai vẫn được đưa ra. Cờ CRC chỉ có
  ở ISR; `video_out` không đánh dấu line đó (§4.7).
- **Cách đọc, chưa kiểm:** FIFO mỗi lane của controller sâu khoảng 18 phần tử. Lane 0 thiếu một burst, nên FIFO của lane
  1–3 đầy, đuôi packet 5 và đầu packet 6 bị mất, và hai packet bị ghép thành một line. Controller căn lại ở packet 7.
- **Chưa biết** D-PHY của AMD xử lý lỗi sync ra sao. Bench không cài được lỗi sync vào line của TX AMD.
- Trong burst có lỗi sync, khối chỉnh giữ `rxactivehs` ở 0. Cách khác, nâng `rxactivehs` cùng `errsotsynchs`, chưa
  được thử.

### 4.6 Số đo theo rate

`tn2b_evidence.py report`, trên các run có frame của E2b-1 (min..max):

| | 260 Mb/s | 800 Mb/s | 1440 Mb/s | 1500 Mb/s |
|---|---|---|---|---|
| Run | SH_E2b-4a, SH_M_E2b-4a | SH_E2b-4b, SH_M_E2b-4b | SH_E2b-1, SH_E2b-2a, SH_E2b-2b và `M_` của chúng | SH_E2b-4c, SH_M_E2b-4c |
| `init_done` của TX (µs) | 392,758 | 570,463 | 383,263 | 380,538 |
| Controller TX xin HS clock (µs) | 394,585 | 571,880 | 384,593 | 381,861 |
| Trailer mỗi packet, PPI của R-X (byte, tổng 4 lane) | 8 | 40 | 72 | 72–74 |
| Trailer mỗi packet, PPI vào R-F (byte, tổng 4 lane) | 0 sau `IBUFDS_DPHY`, 0–8 sau `afe_model` | 0 | 0 | 0 |
| Burst của một line trên PPI của TX (ns) | 6708 | 2300–2470 | 1400–1572 | 1349–1520 |
| Độ trễ của SOF đầu, TX → `video_out` của R-X / R-F (ns) | 2926 / 3874 | 1822 / 2138 | 1654 / 1834 | 1638 / 1810 |
| R-F trễ hơn R-X (ns) | 948 | 316 | 180 | 172 |

- Controller của AMD bỏ được byte trailer của cả hai PHY.
- R-F trễ hơn R-X khoảng 31–32 byte time ở mọi rate. Con số này bằng độ trễ thêm TN2a đo ở PPI, tức đến từ delay line
  cắt trailer của `ftel_dphy_rx`, không phải từ controller.
- Độ trễ của các line sau tăng dần, tới 26 µs ở 1440 Mb/s, vì TX nhận line ở AXI4-Stream nhanh hơn tốc độ dây và giữ
  chúng trong line buffer. Hai RX tăng như nhau.

### 4.7 Các điểm khác

- **`tuser[1]` ở `video_out` luôn bằng 0** với dữ liệu pixel. Trong RTL của frame buffer (`vfb_v1_0`, Vivado 2025.2),
  đầu ra ghép thành `{ECC/CRC, 2'b0, DT, WC, line, frame, 15'h0, SOF}`; cờ lỗi từ controller chỉ dùng để kết thúc line,
  và chỉ đi tiếp với data type user-defined. Lỗi payload vẫn bị bắt ở ba chỗ: so pixel với golden, CRC trên PPI, thanh
  ghi CRC (NEG-crc). Ở TN3, ILA trên `video_out` không tự thấy line hỏng; cần đọc ISR, hoặc bắt cả PPI.
- **TX Subsystem chỉ gửi FE của một frame khi bắt đầu frame kế,** với `C_EN_REG_BASED_FE_GEN` để mặc định false. Vì vậy
  frame cuối của mỗi run không có FE trên cả ba PPI; ở E2b-8 thiếu thêm FE của frame 0, vì TX tắt trước frame 1. R-X và
  R-F thấy giống nhau. Nguyên nhân chưa đọc được, vì RTL của TX đã mã hoá. Ở TN3 bên phát là camera, nên điều này chỉ
  thuộc bench.

### 4.8 Trả lời bốn câu hỏi của TN2b

1. **R-X: có**, ở mọi run. **R-F: không, khi nối thẳng** (§4.1). **R-F qua khối chỉnh: có**, ở 27/27 run (§4.3). Thanh
   ghi sạch ở mọi run được chấm, trừ các bit dự trữ X của ISR R-F (§4.4).
2. **Có, khi đầu burst được chỉnh:** cùng chuỗi packet, cùng packet count, cùng image info, cùng cờ lỗi. Byte trailer
   của hai PHY đều được bỏ.
3. **Có.** Chuỗi cấu hình của AMD chạy khi byte clock của `ftel_dphy_rx` chưa chạy, và cả khi RX được cấu hình giữa
   frame. Thứ tự đề xuất cho TN3 ở §4.4.
4. **Cấu hình ở [`TN2_DESCRIPTION.md`](TN2_DESCRIPTION.md) §5.2**, in trong dòng `EXP2B` của từng build và được check
   `config` kiểm ở mọi lần kiểm chứng. Đây là cấu hình dùng cho đặc tả TN3.

## 5. Vì sao tin được kết quả

Mỗi bench có một script kiểm chứng, kiểm lại toàn bộ output bằng code riêng, không dùng chung với bộ so `csi2_dump.py`.
Ngày 2026-10-26 cả hai được chạy lại trên output đã lưu.

### 5.1 TN2a: [`tn2a_evidence.py`](tn2a_evidence.py), **EVIDENCE: PASS (10/10 checks)**

| Check | Kiểm gì | Kết quả |
|---|---|---|
| `checker` | Selftest của `csi2_dump.py`: tìm được các lỗi cài sẵn; capture sạch thì đạt | PASS |
| `decode` | Giải mã lại mọi capture bằng bộ giải mã của `tn1_evidence.py` (viết riêng, không chung code với `csi2_dump.py`), kể cả timing ở PPI; kết quả phải trùng `check.txt` | 120/120 capture |
| `runs` | Đủ 60 run; mọi run kết thúc bình thường, truth có một dòng cho mỗi burst và lane; mọi kịch bản đạt cả `check.txt` lẫn `tbcheck.txt` | 60/60 run |
| `tx` | Ở mọi run từ TX, byte trên pad bằng byte đã giao cho TX. NEG-tx: đúng một byte khác, đúng chỗ đã cài (`8f` trên pad thay cho `70`), và hai RX vẫn khớp pad | 54 run, cộng NEG-tx |
| `padtruth` | Mọi run từ line generator: `truth.txt` trùng `truth_gen.txt` | 6 run, lệch 0 ps |
| `front` | Đầu ra LP của hai bộ buffer trùng nhau ở mọi lần đổi sau 2,5 ps. NEG-front phải đếm ra khác biệt, trong khi RX AMD vẫn đạt | 59 run, 2 812 162 lần so, 0 khác; NEG-front 25 744 / 32 674 |
| `afe` | `afe_model` không lỗi trạng thái; `term_en` không trễ, không thiếu | 59/59 run |
| `config` | Cấu hình RX mình đúng giá trị model của HAS ở rate đó, hoặc giá trị kịch bản đặt | 60/60 run |
| `sources` | Mã băm nguồn ghi trong từng run bằng mã băm nguồn hiện tại | 60/60 run |
| `copy` | Ba khối lấy từ testbench của TN1 vẫn trùng nguyên văn | 29, 15 và 59 dòng code |

### 5.2 TN2b: [`tn2b_evidence.py`](../exp2b/tn2b_evidence.py), **EVIDENCE: PASS (12/12 checks)**

| Check | Kiểm gì | Kết quả |
|---|---|---|
| `checker` | Selftest của `csi2_dump.py` | PASS |
| `decode` | Giải mã lại mọi capture bằng bộ giải mã riêng (ECC sửa 1 bit như receiver; CRC; timing ở PPI); mỗi mục của `check.txt` phải cùng kết luận; ba golden trùng nhau, PPI của TX và R-X trùng golden; selftest của bộ giải mã (15 ca, có ví dụ CRC và ECC của CSI-2 v1.3) | 277/277 mục, 40 run |
| `runs` | Đủ 40 run; mọi run kết thúc bình thường; mọi kịch bản `SH_*` đạt cả `check.txt` lẫn `tbcheck` (E2b-9: `tbcheck`; phần R-F do `gate` chấm) | 40/40 run |
| `regs` | Ở mọi kịch bản được chấm: hai RX frame received, không cờ lỗi, R-F bằng R-X; liệt kê run chỉ báo cáo và bit X | 24 run chấm, 4 run báo cáo |
| `front` | Như TN2a | 39 run, 6 995 053 lần so, 0 khác |
| `afe` | `term_en` không trễ, không thiếu | 39/39 run |
| `config` | Cấu hình RX mình đúng model của HAS; tham số của ba subsystem ở 4 build đúng [`TN2_DESCRIPTION.md`](TN2_DESCRIPTION.md) §5.2 | 40 run, 4 build |
| `sources` | Mã băm nguồn ghi trong từng run bằng mã băm nguồn hiện tại, kể cả khối chỉnh | 40/40 run |
| `copy` | Ba khối lấy từ testbench của TN1 chỉ khác đúng các dòng đã liệt kê | 29, 15 và 59 dòng code |
| `neg` | NEG-ecc, NEG-crc, NEG-front hỏng đúng chỗ, như §4.3 | 3/3 |
| `finding` | 5 run không có khối chỉnh đúng dấu hiệu của §4.1; 4 run chẩn đoán đúng quy luật; ở mọi run `SH_*` (trừ NEG-front), `rxactivehs` vào R-F lên cùng `rxsynchs` | đúng; 30 run `SH_*` |
| `gate` | Mọi run `SH_*` lấy `rxactivehs` từ khối chỉnh, trùng model của testbench ở mọi byte clock. E2b-9: chỉ burst đã định bị đổi; R-X đạt; R-F ra đúng các frame sau frame lỗi, và run kết thúc | 31 run, 436 865 byte clock, 0 khác; E2b-9 phục hồi |

### 5.3 Bộ kiểm có biết báo FAIL không

- **Phép thử âm trong bench:** NEG-tx và NEG-front (TN2a), NEG-ecc, NEG-crc và NEG-front (TN2b) hỏng đúng chỗ đã cài.
  NEG-crc chỉ ra đúng pixel chứa bit cài.
- **Selftest của các bộ so:** `csi2_dump.py` bắt đủ các lỗi cài sẵn, kể cả ca chỉ sai thời gian. Bộ giải mã của TN2b tự
  thử trên các ví dụ CRC và ECC của CSI-2 v1.3 và trên capture giả.
- **`evselftest`:** mỗi script kiểm chứng được thử trên bản copy của output thật, mỗi lần cài một lỗi; mỗi lỗi phải làm
  hỏng đúng check của nó, không thừa, không thiếu, và khi không cài lỗi thì mọi check đạt. Ngày 2026-10-26: TN2a 12
  lỗi, PASS; TN2b 19 lỗi, PASS. Ví dụ ở TN2b: một pixel lật bit, một line bị bỏ, một bit CRC bật trong ISR, khối chỉnh
  khác model một lần, `rxactivehs` lên trong burst có lỗi sync.
- **Kiểm lại không mô phỏng** (`recheck`): TN2a 6 s, TN2b 31 s. Ngày 2026-10-26, 80 file của TN2b viết lại trùng từng
  byte với bản trước.

### 5.4 Hai lỗ hổng của bộ so do team FPGA tìm ra

Ngày 2026-10-26, tester của team FPGA cho thấy bộ so cũ không kiểm độ rộng và vị trí của `rxsynchs`, và không kiểm
lệch giữa các lane ([`../exp1/TN1_REPORT.md`](../exp1/TN1_REPORT.md) §5).
- Bộ so `csi2_dump.py` và bộ giải mã của cả hai script kiểm chứng nay kiểm cả hai luật.
- Ba lỗi giống các lỗi tester đã cài nằm trong `evselftest` của TN2a và TN2b, và đều bị bắt.
- Mọi run của TN2a và TN2b đạt cả hai luật (§3.5). Ở PPI vào R-F của TN2b, `rxsynchs` cùng chu kỳ với byte đầu, và
  lệch giữa các lane bằng 0 ở mọi run `SH_*` có nhiều lane, trừ NEG-front.

## 6. Giới hạn

1. TX, RX AMD, ba subsystem và `IBUFDS_DPHY` đều là model mô phỏng của AMD, không phải phần cứng. RTL của các controller
   CSI-2 đã mã hoá: quy luật đầu burst ở §4.1 được tìm bằng thử, không đọc từ RTL.
2. Front end chung là model của AMD: trong HS, LP đổi theo data, còn silicon cho LP-00. Bộ phụ `M_*` phủ trường hợp
   LP-00, và RX mình đạt ở cả hai.
3. Timing của TX không chỉnh được, nên mỗi rate chỉ có một điểm timing. TX trong mô phỏng không có skew giữa lane và
   không có jitter. TN1 đã phủ các góc timing và skew.
4. RTL mô phỏng zero-delay, không có metastability. CDC của các ngõ ra không đồng bộ của RX mình thuộc phân tích CDC của
   build FPGA.
5. TN2b chỉ có một TX, một kiểu frame (RAW10, VC 0, continuous clock) và frame tổng hợp, chưa có frame camera.
6. Khối chỉnh đã được kiểm riêng, synth và mô phỏng trong TN2b, nhưng chưa chạy trên board.
7. RTL `ftel_dphy_rx` chưa được synth bằng Vivado; bench XSIM compile nó với `--relax`
   ([`TN2_DESCRIPTION.md`](TN2_DESCRIPTION.md) §12).

**Độ tin cậy:**
- **HIGH:**
  - PASS là thật trong điều kiện đã mô phỏng;
  - timing TX là số đo trên pad;
  - hai RX cùng front end (kiểm ở mọi run, có phép thử âm);
  - quy luật "`rxactivehs` không lên trước `rxsynchs`" của controller AMD: đúng ở 4 rate, 4 run chẩn đoán và 30 run qua
    khối chỉnh;
  - `tuser[1]` = 0 (đọc RTL của frame buffer); bit 27:23 không được driver của AMD định nghĩa.
- **MED:**
  - cách đọc kết quả E2b-9 (FIFO của lane đầy): chỉ là giải thích, chưa kiểm;
  - nguyên nhân TX chỉ gửi FE khi có frame kế: quan sát chắc, nguyên nhân là đoán;
  - controller AMD trên silicon xử lý đầu burst như model.
- **LOW:** chuyển kết luận sang board khi chưa có TN3.

## 7. Việc tiếp theo

- **TN3 (trên board):** đặc tả ở [`../exp3/TN3_SPEC.md`](../exp3/TN3_SPEC.md); bản 0.2 đã có khối chỉnh trong R-F.
  Các mục về design TX và RX sẽ dùng cấu hình ba subsystem và thứ tự cấu hình của TN2b (§4.4, §4.8).
- **Bản FPGA của RX mình**, trong đó XPHY thay khối lấy mẫu và giải nối tiếp: chưa lên lịch. Cách cho Vivado đọc RTL
  `ftel_dphy_rx` mà không sửa RTL sẽ được chốt ở bước này, hoặc khi build design cho TN3.

## 8. Số liệu gốc

- Output nằm ở `fpga/work/exp2/` và `fpga/work/exp2b/` trên máy của nhóm D-PHY RX, không có trong repo (git bỏ qua):
  khoảng 0,5 GB cho TN2a và 0,8 GB cho TN2b, kể cả build. Bản lưu của 39 run TN2b ngày 2026-10-23 nặng thêm khoảng
  0,45 GB.
- Có hai cách lấy số liệu:
  - chạy lại theo [`TN2_DESCRIPTION.md`](TN2_DESCRIPTION.md);
  - xin nhóm một bản copy.
- Ghi chép kỹ thuật chi tiết hơn, có dùng thuật ngữ nội bộ của nhóm: [`README.md`](README.md) (TN2a) và
  [`../exp2b/README.md`](../exp2b/README.md) (TN2b).
