# TN1 — Báo cáo thí nghiệm: RX D-PHY `ftel_dphy_rx` so với RX D-PHY của AMD (mô phỏng XSIM)

> Báo cáo kết quả TN1 cho team FPGA. Cách dựng bench và cách chạy lại nằm ở
> [`TN1_DESCRIPTION.md`](TN1_DESCRIPTION.md).
> Lần chạy: 2026-10-20, RTL `ftel_dphy_rx` theo HAS v0.16, giống RTL trên nhánh `dev` của repo fu3_dphy từ commit
> `66f9f39`. Output được kiểm lại ngày 2026-10-22: 227/227 run PASS, kiểm chứng 8/8.
> Phiên bản 1.0, ngày 2026-10-22. Nhóm D-PHY RX viết.

## 1. Tóm tắt

- **Kết quả:** 113/113 kịch bản PASS cho cả hai RX, khi RX mình đứng sau cùng buffer `IBUFDS_DPHY` như RX AMD. Bộ
  chạy phụ, với RX mình đứng sau mô hình AFE, cũng đạt 113/113. Ở 80 Mb/s, ngoài dải bảo đảm, RX mình vẫn nhận nguyên
  payload của 36/36 burst-lane.
- **Phạm vi đã thử:**
  - 8 rate từ 260 tới 1500 Mb/s; 1, 2 và 4 lane;
  - payload `counter`, PRBS-9, và payload có mẫu giống sync;
  - timing D-PHY ở biên min và max, skew 0,2 UI;
  - nhiễu trước HS và ở cuối burst; `core_clk` lệch 400 ppm so với line.
- **Payload:** cùng front end và cùng kịch bản, phần digital của RX mình nhận đúng mọi payload như phần digital của
  RX AMD.
- **Hai điểm khác nhau, đều do thiết kế:**
  - Trailer: RX mình cắt bỏ byte thừa sau payload; RX AMD giữ lại, tới 25 byte mỗi burst ở 1500 Mb/s.
  - Độ trễ: RX mình trễ hơn khoảng 6–7 lần (201–206 ns so với 27–32 ns ở 1440 Mb/s), vì delay line 32 byte dùng để
    cắt trailer.
- **Lỗi tìm ra:** ở lần chạy đầu, RX mình có hai lỗi RTL. Cả hai đã được sửa trong HAS v0.16 và không còn xuất hiện
  (§4).
- **Giới hạn chính:** cả hai front end đều là mô hình, nên kết luận cho silicon còn cần thí nghiệm trên board (TN3).

## 2. Thí nghiệm

Một line generator trong testbench phát tín hiệu D-PHY vào cùng lúc RX AMD (`mipi_dphy` 4.3, SLAVE) và RX mình (RTL
ASIC, không sửa).
- RX mình đứng sau `IBUFDS_DPHY`, đúng buffer mà IP AMD dùng, với cùng strength trên pad. Ở mọi run, bench kiểm rằng
  đầu ra LP của hai bộ buffer trùng nhau.
- PPI của mỗi RX được ghi ra CSV định dạng ILA và so với file truth bằng cùng một bộ luật. Bộ luật xét số burst,
  payload, thời gian, cờ lỗi và số byte trailer.
- Một kịch bản đạt khi cả hai RX đều 0 lỗi.

```
line generator ──► truth.txt
   ├─► RX AMD (mipi_dphy 4.3) ──────────────────────────► PPI ─► xil_ppi.csv  ─┐
   └─► IBUFDS_DPHY (hoặc afe_model) ─► ftel_dphy_rx ─────► PPI ─► ftel_ppi.csv ─┴─► so với truth.txt
```

Chi tiết bench, luật so và danh sách kịch bản nằm ở [`TN1_DESCRIPTION.md`](TN1_DESCRIPTION.md) §4–§7.

## 3. Kết quả

### 3.1 Các kịch bản E1-1 tới E1-4

Ở mọi kịch bản, cả hai RX nhận đúng toàn bộ payload. Ví dụ ở E1-1, mỗi RX đúng 40/40 burst-lane.

Bảng ghi số byte trailer mỗi burst và độ trễ của byte payload cuối. Cột "sau `afe_model`" là bộ chạy phụ.

| Rate (Mb/s) | Kịch bản | Trailer: AMD | Trailer: RX mình sau `IBUFDS_DPHY` | Trailer: RX mình sau `afe_model` | Độ trễ: AMD | Độ trễ: RX mình |
|---|---|---|---|---|---|---|
| 260 | E1-4a / E1-4a timing min | 2 / 1–2 | 0 / 0 | 0 / 0–2 (ở 8 trong 40 burst) | 152–179 ns | 1113–1140 ns |
| 800 | E1-4b | 9 | 0 | 0 | 50–58 ns | 362–371 ns |
| 1440 | E1-1…E1-3, E1-4d/e | 14–17 | 0 | 0 | 27–32 ns | 201–206 ns |
| 1500 | E1-4c | 17–18 | 0 | 0 | 26–31 ns | 193–198 ns |

Ở 260 Mb/s, giới hạn trailer của RX mình là 4 byte, nên 0–2 byte vẫn đạt.

### 3.2 Stress cuối burst (E1-5)

E1-5 gồm 96 run, chạy cả hai RX:
- 8 rate;
- trail min, mặc định và max;
- có hoặc không có jitter trail (0–7 bit);
- có hoặc không có 40 ns nhiễu ở cuối trail;
- `core_clk` lệch 400 ppm, để LP-11 rơi vào mọi pha của `core_clk`.

Mỗi ô của bảng gộp 3 loại trail × 2 trường hợp jitter, tức 432 burst-lane. **Ở mọi ô, cả hai RX đều nhận đủ 432/432
payload.** Trailer ghi dạng "khoảng (số burst có trailer)". "Giống bên trái" nghĩa là trùng cả khoảng lẫn số burst.

| Rate (Mb/s) | Nhiễu | Trailer: AMD | Trailer: RX mình sau `IBUFDS_DPHY` | Trailer: RX mình sau `afe_model` | Giới hạn của RX mình |
|---|---|---|---|---|---|
| 260 | không | 1–4 | 0 | 0–4 (67) | 4 |
| 260 | 40 ns | 1–4 | 0–4 (429) | giống bên trái | 4 |
| 400 | không | 3–7 | 0 | 0–4 (4) | 6 |
| 400 | 40 ns | 2–7 | 0–5 (426) | giống bên trái | 6 |
| 600 | không | 5–10 | 0 | 0 | 0 |
| 600 | 40 ns | 5–10 | 0–7 (421) | giống bên trái | 7 |
| 800 | không | 7–13 | 0 | 0 | 0 |
| 800 | 40 ns | 6–13 | 0–8 (328) | giống bên trái | 8 |
| 1000 | không | 9–17 | 0 | 0 | 0 |
| 1000 | 40 ns | 8–16 | 0–8 (15) | giống bên trái | 9 |
| 1200 | không / 40 ns | 11–20 | 0 | 0 | 0 / 10 |
| 1440 | không | 14–24 | 0 | 0 | 0 |
| 1440 | 40 ns | 13–24 | 0–12 (4) | giống bên trái | 12 |
| 1500 | không / 40 ns | 14–25 | 0 | 0 | 0 / 12 |

### 3.3 80 Mb/s (R-80, ngoài dải bảo đảm)

IP AMD không build được dưới 260 Mb/s, nên ở 80 Mb/s chỉ chạy RX mình:
- payload nguyên ở 36/36 burst-lane;
- 0–1 byte trailer, ở 10 burst;
- độ trễ 3,6–3,7 µs.

Kết quả này chỉ để báo cáo, không tính đạt hay hỏng.

### 3.4 Đọc kết quả

- **Payload:** ở cả 8 rate, phần digital của RX mình nhận đúng mọi payload như phần digital của RX AMD.
- **Trailer:**
  - RX AMD theo thiết kế không cắt trailer, và số byte thừa tăng theo rate.
  - Không có nhiễu:
    - sau `IBUFDS_DPHY`, RX mình không để lại byte thừa nào ở cả 8 rate;
    - sau `afe_model`, RX mình không để lại byte thừa từ 600 Mb/s trở lên, đúng như HAS bảo đảm. Ở 260 và 400 Mb/s,
      RX mình để lại tới 4 byte, vẫn trong giới hạn.
  - Có 40 ns nhiễu, RX mình vẫn nằm trong giới hạn của HAS ở mọi rate.
  - Sau `IBUFDS_DPHY`, RX mình để lại ít hoặc bằng số byte trailer so với khi đứng sau `afe_model`. Lý do: model của
    AMD giữ bit trail sau LP-11, còn `afe_model` ép về 0. Giới hạn trong HAS được đo sau `afe_model`, nên đó vẫn là
    trường hợp xấu hơn.
- **Độ trễ:** RX mình trễ hơn vì delay line 32 byte cần cho phép cắt trailer. Độ trễ không phụ thuộc front end.

## 4. Lỗi TN1 tìm ra và đã sửa

Lần chạy đầu ngày 2026-10-19, với RTL theo HAS v0.15, cùng tín hiệu và cùng bộ kiểm:

| Kịch bản | RX AMD | RX mình |
|---|---|---|
| E1-1 (1440 Mb/s) | 40/40 burst-lane đúng | 20/40 đúng, 28 lỗi |
| E1-3c (timing min) | 16/16 | 0/16, 20 lỗi |
| E1-4b (800 Mb/s) | 40/40 | 0/40, 44 lỗi |

RX AMD đạt, nên tín hiệu phát ra là đúng và lỗi nằm ở RX mình. Hai nguyên nhân tìm được trong RTL như sau.

**Lỗi 1: cắt trailer làm mất byte payload cuối.**
- **Hiện tượng:** byte payload cuối của burst bị cắt mất. Dưới khoảng 800 Mb/s, không giá trị `eot_skip_bytes` nào
  cắt đúng.
- **Nguyên nhân:** yêu cầu cắt sinh ra khi line về LP-11, và nó tới delay line sớm hơn dữ liệu của cùng thời điểm.
  Công thức tính `eot_skip_bytes` đã bỏ sót độ trễ của đường dữ liệu, khoảng 4–5 byte clock. Ở rate thấp, yêu cầu còn
  tới trước cả khi byte payload cuối vào delay line.
- **Sửa:**
  - giữ burst mở thêm 3 byte clock sau khi phát hiện LP-11, để dữ liệu kịp vào delay line trước khi cắt;
  - tính lại `eot_skip_bytes` từ một hằng số 24 ns, đo trên mọi pha của `core_clk` (xem "Bài học" bên dưới).

**Lỗi 2: một `rxvalidhs` nằm ngoài `rxactivehs` ở cuối mỗi burst.**
- **Hiện tượng:** trên mỗi lane, mỗi burst có đúng một byte được báo valid sau khi `rxactivehs` đã về 0. Byte đó là
  byte sau trail.
- **Nguyên nhân:** ở chu kỳ burst kết thúc, khối tìm sync vẫn đánh dấu một byte mới là valid trong khi cờ active đã
  về 0. Vì vậy byte này lọt qua phép cắt.
- **Sửa:** cờ valid, cờ sync và cờ lỗi SoT chỉ được bật khi burst đang mở.

**Bài học khi đo cửa sổ cắt trailer.**
- Bảng giới hạn trailer và hằng số đầu tiên (27 ns) được đo khi `core_clk` chạy đúng tỉ lệ cố định với line. Khi đó
  LP-11 chỉ rơi vào vài pha của `core_clk`.
- Một lần chạy lại với seed khác hỏng 2 run E1-5 và làm lộ ra điều này: hằng số 27 ns không còn biên ở 600, 800 và
  1440 Mb/s.
- Đo lại với `core_clk` lệch 400 ppm, jitter trail 0–7 bit và 1120 burst mỗi ô thì ra hằng số 24 ns.
- Biên đã được đo, không giả định: với trail min, giá trị model + 1 không bao giờ mất payload, còn model + 2 mất
  payload ở mọi rate.

**Front end chung cho hai RX.**
- IP AMD đưa pad tới `IBUFDS_DPHY` qua một `assign` thường, nên buffer của nó luôn thấy strength strong. Trong XSIM,
  đầu ra LP của buffer vì thế đổi theo data khi HS.
- Để so công bằng, RX mình được đặt sau đúng buffer đó, với cùng strength.
- Phương án lái pad bằng strength pull trong HS bị loại, vì nó chỉ thay đổi buffer của RX mình.

**Ghép burst theo thời gian.**
- Payload có thể lặp lại, vì mẫu `counter` quay vòng sau 16 burst. Khi đó, ghép burst chỉ theo thứ tự có thể che mất
  trường hợp một burst bị mất và một burst khác bị thừa.
- Bộ so đã được thêm luật thời gian ([`TN1_DESCRIPTION.md`](TN1_DESCRIPTION.md) §6).
- Toàn bộ 355 run đã được kiểm lại theo luật mới: không kết luận nào đổi.

## 5. Vì sao tin được kết quả

[`tn1_evidence.py`](tn1_evidence.py) kiểm lại toàn bộ output bằng code riêng, không dùng chung với bộ so. Ngày
2026-10-22, trên output của lần chạy 2026-10-20, kết quả là **EVIDENCE: PASS (8/8 checks)**.

| Check | Kiểm gì | Kết quả |
|---|---|---|
| `checker` | Selftest của bộ so: tìm được các lỗi cài sẵn, kể cả ca chỉ sai thời gian; capture sạch thì đạt | PASS |
| `decode` | Giải mã lại mọi capture bằng code riêng; kết quả phải trùng `check.txt` | 453/453 capture của 227 run |
| `runs` | Mọi run kết thúc bình thường; file truth có đủ dòng cho mỗi burst và lane | 227/227 run |
| `front` | Đầu ra LP của hai bộ buffer trùng nhau ở mọi lần đổi | 226/226 run, 4 854 302 lần đổi, 0 khác |
| `afe` | Mô hình AFE không báo lỗi trạng thái; tín hiệu bật terminal không trễ, không thiếu | 227/227 run |
| `config` | Cấu hình RX mình đúng giá trị model cho rate đó, hoặc giá trị kịch bản đặt | 227 run |
| `sources` | Mã băm nguồn của mọi build bằng mã băm nguồn hiện tại | 11/11 build |
| `margin` | Với trail min, `eot_skip_bytes` model + 1 không mất payload, model + 2 có mất | 8/8 rate |

Các bộ kiểm cũng được thử xem có biết báo FAIL không:
- Bộ so bắt đủ 4 lỗi cài sẵn: đảo một byte, mất một burst, cờ lỗi SoT, sync hai lần. Luật thời gian bắt được ca mất một
  burst rồi thừa một burst cùng payload.
- Check `front` báo FAIL khi buffer của RX mình bị lái khác đi. Phép thử âm [`neg_front.sh`](neg_front.sh) cho 21 574
  trong 30 450 lần đổi khác nhau.
- Đổi 1 bit payload trong một capture thì check `decode` báo FAIL.
- Đặt `eot_skip_bytes` bằng model + 2 thì mất payload ở mọi rate, ví dụ 711 burst ở 260 Mb/s.
- Lần chạy đầu với RTL cũ hỏng như ở §4. PASS chỉ xuất hiện sau khi sửa code, và các chỗ sửa giải thích được các lỗi
  đã thấy.

## 6. Giới hạn

1. Front end chung là mô hình mô phỏng của AMD, không phải AFE thật. Trong HS, mô hình cho LP đổi theo data, còn
   silicon cho LP-00. Bộ chạy phụ sau `afe_model` phủ trường hợp LP-00, và RX mình đạt ở cả hai.
2. `afe_model` là AFE lý tưởng do nhóm viết. Độ giống AFE thật chỉ kiểm được trên phần cứng.
3. RX AMD trong XSIM là mô hình mô phỏng của IP, không phải phần cứng.
4. RTL mô phỏng zero-delay, không có metastability. Phần này thuộc phân tích CDC và STA.
5. Chỉ kiểm theo kịch bản, không đo functional coverage.
6. Chưa kiểm: ULPS, escape mode, deskew, non-continuous clock, packet CSI-2, hiệu ứng analog (jitter, ISI), lỗi bit
   chèn vào. `stopstate` có ghi nhưng không so.

**Độ tin cậy:**
- **HIGH:** PASS là thật trong điều kiện đã mô phỏng; hai RX thật sự cùng front end (đọc từ mã nguồn IP, kiểm ở mọi
  run, có phép thử âm).
- **MED:** số byte trailer tối đa, vì công thức giới hạn trong HAS có một hằng số khớp từ số đo.
- **LOW:** chuyển kết luận sang silicon, vì cả hai front end đều là mô hình.

## 7. Việc tiếp theo

TN1 đã xong. Các bước sau chưa lên lịch:
- **TN2 (mô phỏng):**
  - TX D-PHY của AMD phát vào cả hai RX;
  - CSI-2 TX phát frame. Một nhánh là CSI-2 RX có PHY của AMD; nhánh kia là RX mình nối vào CSI-2 RX không có PHY. Hai
    nhánh được so từng frame;
  - bản FPGA của RX mình, trong đó XPHY thay khối lấy mẫu và giải nối tiếp.
- **TN3 (trên board):** TX trên một board FPGA thứ hai có FMC chạy được 1,2 V → mạch test → RX trên board VP1902.
  Phần 1 của đặc tả nằm ở [`fpga/exp3/TN3_SPEC.md`](../exp3/TN3_SPEC.md).

## 8. Số liệu gốc

- Output của lần chạy nằm ở `fpga/work/exp1/` trên máy của nhóm D-PHY RX. Thư mục này không có trong repo (git bỏ qua)
  và nặng khoảng 1,7 GB, gồm cả bản lưu của lần chạy đầu.
- Có hai cách lấy số liệu:
  - chạy lại theo [`TN1_DESCRIPTION.md`](TN1_DESCRIPTION.md);
  - xin nhóm một bản copy.
- Ghi chép kỹ thuật chi tiết hơn, có dùng thuật ngữ nội bộ của nhóm: [`README.md`](README.md).
