# TN1 - Báo cáo thí nghiệm: RX D-PHY `ftel_dphy_rx` so với RX D-PHY của AMD (mô phỏng XSIM)

> Báo cáo kết quả TN1 cho team FPGA. Cách dựng bench và cách chạy lại nằm ở
> [`TN1_DESCRIPTION.md`](TN1_DESCRIPTION.md).
> Lần chạy: 2026-10-20, RTL `ftel_dphy_rx` theo HAS v0.16, giống RTL trên nhánh `dev` của repo fu3_dphy từ commit
> `66f9f39`. Output được kiểm lại ngày 2026-10-22: 227/227 run PASS, kiểm chứng 8/8.
> Chạy lại toàn bộ ngày 2026-10-26 trong repo fu3_dphy, cùng RTL, với bộ so có thêm hai luật timing ở PPI (§5): 227
> run cho kết quả như cũ, output trùng từng byte với lần chạy 2026-10-20; thêm 3 run lệch lane (§3.4); kiểm chứng 8/8.
> Chạy lại toàn bộ ngày 2026-11-03 trên RTL theo HAS v0.17, trong đó lane về trạng thái Stop ngay sau mỗi burst (§4):
> ngoài cột `stopstate`, mọi capture trùng lần chạy 2026-10-26; thêm 49 run burst sát nhau (§3.6); kiểm chứng 9/9.
> Phiên bản 1.2, ngày 2026-11-03 (1.1: 2026-10-26, 1.0: 2026-10-22). Nhóm D-PHY RX viết.

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
  - Độ trễ: RX mình trễ hơn khoảng 6-7 lần (201-206 ns so với 27-32 ns ở 1440 Mb/s), vì delay line 32 byte dùng để
    cắt trailer.
- **Lỗi tìm ra:** ở lần chạy đầu, RX mình có hai lỗi RTL. Cả hai đã được sửa trong HAS v0.16 và không còn xuất hiện
  (§4). Lỗi thứ ba, bỏ lỡ burst khi hai burst sát nhau ở rate thấp, được sửa trong HAS v0.17 (§4).
- **Giới hạn chính:** cả hai front end đều là mô hình, nên kết luận cho silicon còn cần thí nghiệm trên board (TN3).
- **Cập nhật 2026-10-26:**
  - Team FPGA tìm ra hai lỗ hổng của bộ so: độ rộng và vị trí của `rxsynchs`, và lệch giữa các lane. Cả hai đã được sửa.
  - Toàn bộ TN1 chạy lại: không kết luận nào đổi, và RX mình đạt cả hai luật mới ở mọi run (§5).
  - Ba run mới cho lane lệch lớn: hai run trong giới hạn 6 byte clock đạt; run vượt giới hạn hỏng đúng ở luật lệch
    lane (§3.4).
- **Cập nhật 2026-11-03:**
  - Tester của team FPGA chỉ ra một mâu thuẫn trong HAS v0.16: dải rate hứa 80-1792 Mb/s, nhưng ở rate thấp lane có
    thể bỏ lỡ burst khi hai burst sát nhau. Bộ chạy mới `lowgap` xác nhận: với khe tối thiểu giữa hai burst, RTL cũ
    chỉ nhận 16/32 burst mỗi lane ở 80 và 120 Mb/s, 24/32 ở 160 Mb/s.
  - RTL theo HAS v0.17 sửa lỗi này. Ở 13 rate từ 80 tới 1792 Mb/s, RX mình nhận đủ 32/32 burst mỗi lane (§3.6).
  - Tham số tổng hợp mới `PARA_STOP_DRAIN_EN` chọn lúc `stopstate` lên. Hai giá trị cho cùng dữ liệu ở PPI, chỉ khác
    ở `stopstate` (§3.6).
  - Toàn bộ TN1 chạy lại trên RTL mới: ngoài cột `stopstate`, mọi capture trùng lần chạy trước (§3.6); kiểm chứng 9/9
    (§5).

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

Chi tiết bench, luật so và danh sách kịch bản nằm ở [`TN1_DESCRIPTION.md`](TN1_DESCRIPTION.md) §4-§7.

## 3. Kết quả

### 3.1 Các kịch bản E1-1 tới E1-4

Ở mọi kịch bản, cả hai RX nhận đúng toàn bộ payload. Ví dụ ở E1-1, mỗi RX đúng 40/40 burst-lane.

Bảng ghi số byte trailer mỗi burst và độ trễ của byte payload cuối. Cột "sau `afe_model`" là bộ chạy phụ.

| Rate (Mb/s) | Kịch bản | Trailer: AMD | Trailer: RX mình sau `IBUFDS_DPHY` | Trailer: RX mình sau `afe_model` | Độ trễ: AMD | Độ trễ: RX mình |
|---|---|---|---|---|---|---|
| 260 | E1-4a / E1-4a timing min | 2 / 1-2 | 0 / 0 | 0 / 0-2 (ở 8 trong 40 burst) | 152-179 ns | 1113-1140 ns |
| 800 | E1-4b | 9 | 0 | 0 | 50-58 ns | 362-371 ns |
| 1440 | E1-1…E1-3, E1-4d/e | 14-17 | 0 | 0 | 27-32 ns | 201-206 ns |
| 1500 | E1-4c | 17-18 | 0 | 0 | 26-31 ns | 193-198 ns |

Ở 260 Mb/s, giới hạn trailer của RX mình là 4 byte, nên 0-2 byte vẫn đạt.

### 3.2 Stress cuối burst (E1-5)

E1-5 gồm 96 run, chạy cả hai RX:
- 8 rate;
- trail min, mặc định và max;
- có hoặc không có jitter trail (0-7 bit);
- có hoặc không có 40 ns nhiễu ở cuối trail;
- `core_clk` lệch 400 ppm, để LP-11 rơi vào mọi pha của `core_clk`.

Mỗi ô của bảng gộp 3 loại trail × 2 trường hợp jitter, tức 432 burst-lane. **Ở mọi ô, cả hai RX đều nhận đủ 432/432
payload.** Trailer ghi dạng "khoảng (số burst có trailer)". "Giống bên trái" nghĩa là trùng cả khoảng lẫn số burst.

| Rate (Mb/s) | Nhiễu | Trailer: AMD | Trailer: RX mình sau `IBUFDS_DPHY` | Trailer: RX mình sau `afe_model` | Giới hạn của RX mình |
|---|---|---|---|---|---|
| 260 | không | 1-4 | 0 | 0-4 (67) | 4 |
| 260 | 40 ns | 1-4 | 0-4 (429) | giống bên trái | 4 |
| 400 | không | 3-7 | 0 | 0-4 (4) | 6 |
| 400 | 40 ns | 2-7 | 0-5 (426) | giống bên trái | 6 |
| 600 | không | 5-10 | 0 | 0 | 0 |
| 600 | 40 ns | 5-10 | 0-7 (421) | giống bên trái | 7 |
| 800 | không | 7-13 | 0 | 0 | 0 |
| 800 | 40 ns | 6-13 | 0-8 (328) | giống bên trái | 8 |
| 1000 | không | 9-17 | 0 | 0 | 0 |
| 1000 | 40 ns | 8-16 | 0-8 (15) | giống bên trái | 9 |
| 1200 | không / 40 ns | 11-20 | 0 | 0 | 0 / 10 |
| 1440 | không | 14-24 | 0 | 0 | 0 |
| 1440 | 40 ns | 13-24 | 0-12 (4) | giống bên trái | 12 |
| 1500 | không / 40 ns | 14-25 | 0 | 0 | 0 / 12 |

### 3.3 80 Mb/s (R-80, ngoài dải bảo đảm)

IP AMD không build được dưới 260 Mb/s, nên ở 80 Mb/s chỉ chạy RX mình:
- payload nguyên ở 36/36 burst-lane;
- 0-1 byte trailer, ở 10 burst;
- độ trễ 3,6-3,7 µs.

Kết quả này chỉ để báo cáo, không tính đạt hay hỏng.

### 3.4 Lệch lớn giữa các lane (E1-6a, E1-6b, NEG-skew; thêm ngày 2026-10-26)

Ở 1440 Mb/s (một byte time là 5,556 ns), cặp dây của lane 3 được làm trễ so với ba lane kia. Không RX nào căn lại các
lane, nên độ lệch tới thẳng PPI. Bộ so kiểm rằng trong mỗi burst, byte thứ k tới PPI trên các lane lệch nhau tối đa 6
byte clock (HAS, bảng A-2).

| Run | Lane 3 trễ | Lệch đo ở PPI: AMD | Lệch đo ở PPI: RX mình | Payload, mỗi RX | Kết quả |
|---|---|---|---|---|---|
| E1-6a | 13 889 ps (2,5 byte time) | 3 byte clock | 2-3 byte clock | 16/16 burst-lane | PASS |
| E1-6b | 30 556 ps (5,5 byte time) | 6 | 5-6 | 16/16 | PASS |
| NEG-skew | 41 667 ps (7,5 byte time) | 8 | 7-8 | 16/16 | FAIL, đúng như định: chỉ luật lệch lane hỏng, 4 lỗi ở mỗi RX (mỗi burst một lỗi) |

- Lệch đo ở PPI bằng độ trễ của lane tính theo byte, làm tròn theo byte clock. RX AMD luôn cho số làm tròn lên; RX
  mình cho số làm tròn lên hoặc xuống, tuỳ burst.
- Khi vượt 6 byte clock, payload của từng lane vẫn đúng. Việc ghép các lane lại là của controller CSI-2 phía sau. HAS
  hiện chỉ đặt giới hạn ở PPI, chưa ghi rõ điều gì xảy ra khi vượt.

### 3.5 Đọc kết quả

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

### 3.6 Burst sát nhau ở mọi rate (LG-*, DR-*, NEG-drain; thêm ngày 2026-11-03)

Mỗi run phát 32 burst trên mỗi lane, 4 lane, payload 1-64 byte. Giữa hai burst, line chỉ ở LP-11 rồi LP-01 trong thời
gian tối thiểu mà D-PHY cho phép: THS-EXIT + TLPX = 100 + 50 ns. Bộ `lowgap` có 24 run: 13 rate từ 80 tới 1792 Mb/s,
cộng 11 biến thể ở 80, 120, 160, 180, 220 và 260 Mb/s (THS-PREPARE + THS-ZERO tối thiểu, THS-TRAIL tối thiểu, hoặc
THS-EXIT 400 ns). Chỉ RX mình chạy, vì IP AMD không build được dưới 260 Mb/s. Kịch bản và lệnh nằm ở
[`TN1_DESCRIPTION.md`](TN1_DESCRIPTION.md) §7-§8.

**Số burst nhận được trên mỗi lane, với khe tối thiểu:**

| Rate (Mb/s) | RTL cũ (HAS v0.16) | RTL mới (HAS v0.17) | Byte trailer, RTL mới |
|---|---|---|---|
| 80 | 16/32 | 32/32 | 0-1 |
| 120 | 16/32 | 32/32 | 0 |
| 160 | 24/32 | 32/32 | 0-2 |
| 180 | 32/32 | 32/32 | 0-2 |
| 200 | 32/32 | 32/32 | 0 |
| 220 | 32/32 | 32/32 | 0-3 |
| 240, 260 | 32/32 | 32/32 | 0 |
| 400, 800, 1440, 1500, 1792 | chưa chạy | 32/32 | 0 |

- **RTL cũ:**
  - burst bị bỏ lỡ không để lại gì ở PPI. Mọi burst nhận được đều đúng payload, không có cờ lỗi;
  - ở 80 Mb/s, số burst tăng theo THS-EXIT: 16/32 ở 100 và 150 ns, 20/32 ở 200 ns, 28/32 ở 250 ns, đủ từ 300 ns;
  - lúc chạy RTL cũ, script chưa có bảng giới hạn trailer theo rate, nên run 180 và 220 Mb/s báo hỏng vì trailer. Số
    burst vẫn đủ, và số byte trailer trùng RTL mới.
- **RTL mới:** 24/24 run PASS, mỗi run 128/128 burst-lane, kể cả 11 biến thể. Byte trailer nằm trong giới hạn theo
  rate của script (2-5 byte dưới 260 Mb/s). Giữa hai burst, `rxactivehs` về 0 trong 330-400 ns ở mọi rate.

**`stopstate` và tham số `PARA_STOP_DRAIN_EN`.** Tham số tổng hợp mới này chọn lúc `stopstate` lên:
- 0, mặc định: `stopstate` là trạng thái Stop của lane. Nó lên khoảng 30-35 ns sau khi line về LP-11, trước khi byte
  cuối của burst ra PPI;
- 1: `stopstate` chỉ lên khi mọi output HS của burst đã ra khỏi PPI.

Bộ `drain` chạy lại 24 run của `lowgap` trên bản build với giá trị 1 (DR-*), và kiểm thêm luật `stopstate` của
[`TN1_DESCRIPTION.md`](TN1_DESCRIPTION.md) §6:
- DR-*: 24/24 PASS. Capture của mỗi cặp LG-* và DR-* chỉ khác nhau ở cột `stopstate`, ở cả 24 cặp;
- NEG-drain: run 80 Mb/s của build mặc định, kiểm bằng cùng luật. Nó FAIL đúng như định: payload đúng, chỉ luật
  `stopstate` hỏng, mỗi lane một lỗi.

| Rate (Mb/s) | 0: `stopstate` lên trước byte cuối ra PPI | 1: `stopstate` lên sau mẫu cuối có `rxactivehs` = 1 | 1: số khe giữa hai burst có `stopstate` = 1 |
|---|---|---|---|
| 80 | 34-35 byte clock | 2 byte clock (200 ns) | 0/124 |
| 400 | 30 | 2 (40 ns) | 0/124 |
| 800 | 24-25 | 3 (30 ns) | 0/124 |
| 1500 | 15-17 | 4 (21 ns) | 0/124 |
| 1792 | 11-13 | 4-5 (18-22 ns) | 124/124 |

- Với 0, `stopstate` lên ở mọi khe giữa hai burst. Capture lấy mẫu theo byte clock, nên ở 80 Mb/s với khe tối thiểu
  chỉ thấy 108/124 lần.
- Với 1, ở khe tối thiểu và dưới 1792 Mb/s, lane đã rời trạng thái Stop để nhận burst sau trước khi burst trước ra
  hết PPI. Vì vậy `stopstate` giữ 0 suốt chuỗi burst.
- Với 1, `stopstate` cần byte clock để delay line xả hết. Nếu byte clock dừng trước đó, `stopstate` giữ 0 tới khi byte
  clock chạy lại. Clock liên tục, như ở mọi run TN1, không gặp trường hợp này.

**Hồi quy trên RTL mới.** Cả bộ TN1 chạy lại trên RTL theo HAS v0.17: 230 run của §3.1-§3.4 và 128 run đo cửa sổ cắt
trailer. Capture của RX AMD, file truth và kết quả so trùng từng byte với lần chạy 2026-10-26. Capture của RX mình
trùng ở mọi cột trừ `stopstate`: cột này lên sớm hơn 2-5 byte clock, số lần lên không đổi. Mọi kết luận ở §3.1-§3.5
giữ nguyên.

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
  Công thức tính `eot_skip_bytes` đã bỏ sót độ trễ của đường dữ liệu, khoảng 4-5 byte clock. Ở rate thấp, yêu cầu còn
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
- Đo lại với `core_clk` lệch 400 ppm, jitter trail 0-7 bit và 1120 burst mỗi ô thì ra hằng số 24 ns.
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

**Lỗi 3 (2026-11-03): bỏ lỡ burst khi hai burst sát nhau ở rate thấp.**
- **Hiện tượng:** với khe tối thiểu giữa hai burst, lane chỉ nhận 16/32 burst ở 80 và 120 Mb/s, 24/32 ở 160 Mb/s
  (§3.6). Burst bị bỏ lỡ không để lại gì ở PPI, nên phía sau không biết đã mất burst.
- **Nguyên nhân:** sau LP-11, lane đợi phần nhận HS, chạy theo byte clock, xác nhận đã kết thúc burst rồi mới về
  trạng thái Stop. Ở rate thấp byte clock chậm, nên việc đợi có thể lâu hơn khe giữa hai burst. Trong lúc đợi, yêu cầu
  HS của burst sau (LP-01) đã qua, và lane không nhận burst đó.
- **Tìm ra thế nào:** tester của team FPGA chỉ ra mâu thuẫn trong HAS v0.16, giữa dải rate hứa 80-1792 Mb/s và một
  ghi chú để lane bỏ lỡ burst ở rate thấp. Các kịch bản TN1 trước đó dùng khe mặc định, rộng hơn khe tối thiểu, nên
  không gặp. Bộ `lowgap` được thêm để đo.
- **Sửa (HAS v0.17):** lane về Stop ngay sau LP-11, không đợi; phần nhận HS tự kết thúc burst ở PPI. Tham số
  `PARA_STOP_DRAIN_EN` giữ lựa chọn cho `stopstate` chỉ lên sau khi burst đã ra hết PPI (§3.6).

## 5. Vì sao tin được kết quả

[`tn1_evidence.py`](tn1_evidence.py) kiểm lại toàn bộ output bằng code riêng, không dùng chung với bộ so. Ngày
2026-10-22, trên output của lần chạy 2026-10-20, kết quả là **EVIDENCE: PASS (8/8 checks)**. Ngày 2026-10-26, trên
lần chạy lại, với cả hai luật timing ở PPI: vẫn **PASS (8/8 checks)**. Ngày 2026-11-03, trên RTL theo HAS v0.17:
**PASS (9/9 checks)**, thêm check `lowgap`. Bảng ghi số của hai lần chạy lại.

| Check | Kiểm gì | Kết quả 2026-10-26 | Kết quả 2026-11-03 |
|---|---|---|---|
| `checker` | Selftest của bộ so: tìm được các lỗi cài sẵn, kể cả ca chỉ sai thời gian và ba lỗi tester đã cài; capture sạch thì đạt. Từ 2026-11-03 thêm các ca của luật `stopstate` | PASS | PASS |
| `decode` | Giải mã lại mọi capture bằng code riêng, kể cả vị trí `rxsynchs` và lệch giữa các lane; kết quả phải trùng `check.txt` | 459/459 capture của 230 run | 508/508 capture của 279 run |
| `runs` | Mọi run kết thúc bình thường; file truth có đủ dòng cho mỗi burst và lane; mọi kịch bản đạt, riêng NEG-skew hỏng và chỉ hỏng ở luật lệch lane, NEG-drain hỏng và chỉ hỏng ở luật `stopstate` | 230/230 run | 279/279 run |
| `front` | Đầu ra LP của hai bộ buffer trùng nhau ở mọi lần đổi | 229/229 run, 4 893 764 lần đổi, 0 khác | Như bên trái |
| `afe` | Mô hình AFE không báo lỗi trạng thái; tín hiệu bật terminal không trễ, không thiếu | 230/230 run | 279/279 run |
| `config` | Cấu hình RX mình đúng giá trị model cho rate đó, hoặc giá trị kịch bản đặt | 230 run | 279 run |
| `sources` | Mã băm nguồn của mọi build bằng mã băm nguồn hiện tại | 11/11 build | 12/12 build |
| `margin` | Với trail min, `eot_skip_bytes` model + 1 không mất payload, model + 2 có mất | 8/8 rate | 8/8 rate |
| `lowgap` | Mọi run LG-* và DR-* đủ burst, đúng payload, trailer trong giới hạn; ở DR-*, trên mọi lane, `stopstate` không lên khi burst còn output HS sắp ra PPI, và lên ở cuối capture; mỗi cặp LG-* và DR-* chỉ khác ở cột `stopstate` | - | 48/48 run, 24/24 cặp |

Các con số của 2026-11-03: 279 run = 230 + 24 LG-* + 24 DR-* + NEG-drain; 508 capture = 459 + 49, vì mỗi run mới chỉ
có capture của RX mình; build thứ 12 là bản build với `PARA_STOP_DRAIN_EN` = 1.

Các bộ kiểm cũng được thử xem có biết báo FAIL không:
- Bộ so bắt đủ 4 lỗi cài sẵn: đảo một byte, mất một burst, cờ lỗi SoT, sync hai lần. Luật thời gian bắt được ca mất một
  burst rồi thừa một burst cùng payload. Từ 2026-10-26, bộ so bắt thêm ba lỗi tester đã cài, mỗi lỗi đúng luật của nó.
  Từ 2026-11-03, luật `stopstate` của bộ so đạt với capture có `stopstate` chỉ lên sau khi burst ra hết PPI, và hỏng
  khi `stopstate` lên ngay sau khi burst rời line, hoặc còn 0 ở cuối capture.
- `tn1_evidence.py evselftest` (từ 2026-10-26) cài lần lượt 15 lỗi vào bản copy của output thật, trong đó có ba lỗi
  của tester. Mỗi lỗi làm hỏng đúng check của nó, không thừa, không thiếu; khi không cài lỗi thì mọi check đạt. Từ
  2026-11-03 là 18 lỗi, thêm: mất một burst trong một run `lowgap`; `stopstate` lên trước một burst trong một run
  `drain`; NEG-drain bị ghi là đạt.
- NEG-drain là phép thử âm thật cho luật `stopstate` (§3.6).
- Check `front` báo FAIL khi buffer của RX mình bị lái khác đi. Phép thử âm [`neg_front.sh`](neg_front.sh) cho 21 574
  trong 30 450 lần đổi khác nhau.
- Đổi 1 bit payload trong một capture thì check `decode` báo FAIL.
- Đặt `eot_skip_bytes` bằng model + 2 thì mất payload ở mọi rate, ví dụ 711 burst ở 260 Mb/s.
- Lần chạy đầu với RTL cũ hỏng như ở §4. PASS chỉ xuất hiện sau khi sửa code, và các chỗ sửa giải thích được các lỗi
  đã thấy.

**Hai lỗ hổng của bộ so, do team FPGA tìm ra (2026-10-26).** Một kỹ sư kiểm thử của team FPGA cài lỗi vào bản copy
của capture rồi đưa cho bộ so:
- `rxsynchs` High 3 chu kỳ, hoặc trễ tới byte payload thứ ba: bộ so cũ vẫn đạt, vì nó chỉ đếm cạnh lên của
  `rxsynchs`;
- cả lane 3 trễ 8 chu kỳ: bộ so cũ vẫn đạt, vì mỗi lane chỉ được so với truth của chính nó, không có phép so giữa các
  lane.

Cả hai là lỗ hổng của bộ so, không phải lỗi RTL. Cách sửa:
- bộ so `csi2_dump.py` và script kiểm chứng `tn1_evidence.py` (code riêng) đều kiểm hai luật mới ở
  [`TN1_DESCRIPTION.md`](TN1_DESCRIPTION.md) §6: `rxsynchs` đúng một mẫu và đúng vị trí so với byte đầu; lệch giữa các
  lane tối đa 6 byte clock;
- chính ba lỗi tester đã cài trở thành ca tự thử của cả hai, và mỗi lỗi phải bị bắt;
- NEG-skew là phép thử âm thật cho luật lệch lane (§3.4).

Toàn bộ TN1 được chạy lại với luật mới, và không kết luận nào đổi:
- ở mọi lane burst, RX mình đưa `rxsynchs` đúng một mẫu, cùng chu kỳ với byte đầu; RX AMD đưa trước byte đầu một chu
  kỳ;
- lệch giữa các lane bằng 0 ở mọi run có nhiều lane, trừ E1-6a, E1-6b và NEG-skew, ba run lệch có chủ ý. E1-3d/e/f,
  với skew 139 ps, cũng cho 0.

## 6. Giới hạn

1. Front end chung là mô hình mô phỏng của AMD, không phải AFE thật. Trong HS, mô hình cho LP đổi theo data, còn
   silicon cho LP-00. Bộ chạy phụ sau `afe_model` phủ trường hợp LP-00, và RX mình đạt ở cả hai.
2. `afe_model` là AFE lý tưởng do nhóm viết. Độ giống AFE thật chỉ kiểm được trên phần cứng.
3. RX AMD trong XSIM là mô hình mô phỏng của IP, không phải phần cứng.
4. RTL mô phỏng zero-delay, không có metastability. Phần này thuộc phân tích CDC và STA.
5. Chỉ kiểm theo kịch bản, không đo functional coverage.
6. Chưa kiểm: ULPS, escape mode, deskew, non-continuous clock, packet CSI-2, hiệu ứng analog (jitter, ISI), lỗi bit
   chèn vào. `stopstate` có ghi, nhưng chỉ được so ở các run `drain` (§3.6).
7. `PARA_STOP_DRAIN_EN` = 1 chỉ chạy trong bộ `drain` (4 lane, chỉ RX mình). Mọi bộ khác dùng giá trị mặc định 0.

**Độ tin cậy:**
- **HIGH:** PASS là thật trong điều kiện đã mô phỏng; hai RX thật sự cùng front end (đọc từ mã nguồn IP, kiểm ở mọi
  run, có phép thử âm).
- **MED:** số byte trailer tối đa, vì công thức giới hạn trong HAS có một hằng số khớp từ số đo.
- **LOW:** chuyển kết luận sang silicon, vì cả hai front end đều là mô hình.

## 7. Việc tiếp theo

TN1 đã xong. TN2 (mô phỏng) cũng đã chạy: TX D-PHY của AMD phát vào cả hai RX, rồi CSI-2 TX phát frame vào hai nhánh
CSI-2 RX. Kết quả nằm ở [`../exp2/TN2_REPORT.md`](../exp2/TN2_REPORT.md). Các bước sau chưa lên lịch:
- **Bản FPGA của RX mình (mô phỏng):** XPHY thay khối lấy mẫu và giải nối tiếp.
- **TN3 (trên board):** TX trên một board FPGA thứ hai có FMC chạy được 1,2 V → mạch test → RX trên board VP1902.
  Phần 1 của đặc tả nằm ở [`fpga/exp3/TN3_SPEC.md`](../exp3/TN3_SPEC.md).

## 8. Số liệu gốc

- Output của lần chạy nằm ở `fpga/work/exp1/` trên máy của nhóm D-PHY RX. Thư mục này không có trong repo (git bỏ qua).
  Lần chạy 2026-10-20, kèm bản lưu của lần chạy đầu, nặng khoảng 1,7 GB. Lần chạy lại 2026-10-26 trong repo fu3_dphy
  nặng khoảng 0,8 GB. Lần chạy 2026-11-03 nặng khoảng 0,9 GB; bản lưu của lần chạy 2026-10-26, dùng cho phép so ở
  §3.6, nặng khoảng 0,6 GB.
- Có hai cách lấy số liệu:
  - chạy lại theo [`TN1_DESCRIPTION.md`](TN1_DESCRIPTION.md);
  - xin nhóm một bản copy.
- Ghi chép kỹ thuật chi tiết hơn, có dùng thuật ngữ nội bộ của nhóm: [`README.md`](README.md).
