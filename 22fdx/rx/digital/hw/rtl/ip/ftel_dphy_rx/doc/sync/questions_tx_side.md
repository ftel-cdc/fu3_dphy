# ftel_dphy_rx — Câu hỏi cho phía Tx

| Mục | Nội dung |
|---|---|
| Gửi | Đội phát triển phía Tx (CSI-2 transmitter / D-PHY Tx của sensor) |
| Từ | Nhóm thiết kế D-PHY Rx (`ftel_dphy_rx`) |
| Ngày | 2026-09-26, cập nhật 2026-09-29 (S9: clock lane; S5: THS-EXIT + TLPX ở tốc độ thấp) và 2026-09-30 (S3: vì sao Rx cần continuous clock) |
| Căn cứ | MIPI CSI-2 v1.3, MIPI D-PHY v1.1 (Table 14); HAS của `ftel_dphy_rx` bản nháp v0.8 (`hw/rtl/ip/ftel_dphy_rx/doc/spec.md`; bản Word `FTEL_IP_MIPI_D-PHY_RX_HAS_v0.8.docx`) |

## Bối cảnh

`ftel_dphy_rx` là phần digital của D-PHY receiver ở phía SoC nhận:

```
Tx: CSI-2 protocol ─► D-PHY Tx ══ lane trên PCB ══► AFE ─► ftel_dphy_rx ─► CSI-2 Rx controller
```

Chúng tôi thiết kế Rx theo CSI-2 v1.3 và D-PHY v1.1. Riêng deskew lấy theo D-PHY v1.2, vì cần khi
chạy trên 1.5 Gb/s. Rx được thiết kế để chịu được **toàn bộ dải** min/max của spec, trừ một ngoại lệ
ghi ở S5. Các câu hỏi dưới đây giúp chốt những giá trị mà spec chỉ cho một biên, hoặc để ngỏ.

Mỗi câu hỏi kèm **giả định đang dùng**. Nếu phía Tx đồng ý với giả định, chỉ cần trả lời "Đồng ý".
Một số câu đã có câu trả lời một phần từ HAS của team CSI-2 Rx controller (HAS-CSI); với các câu
đó, chúng tôi chỉ nhờ xác nhận.

**Cần trả lời trước HAS v1.0:** **S4, S5**. Đây là hai mục mở trong HAS, đang chặn 4 yêu cầu.
S1, S3, S9 và S10 cũng cần sớm, để chuẩn bị môi trường verify.

## Tóm tắt

| ID | Chủ đề | Ưu tiên | Trạng thái |
|---|---|---|---|
| S1 | Dải tốc độ lane; có đổi tốc độ khi đang chạy không | Cao | Đã có một phần từ HAS-CSI, nhờ xác nhận |
| S2 | Số data lane cho từng sensor mode | Trung bình | Đã có từ HAS-CSI, nhờ xác nhận |
| S3 | Continuous hay non-continuous clock | Cao | Đã có từ HAS-CSI, nhờ xác nhận |
| S4 | Deskew: có gửi không, pattern, độ dài, thời điểm | **Cao** | Mở |
| S5 | Bảng timing thực tế của Tx (đặc biệt THS-TRAIL max, THS-ZERO max, THS-EXIT + TLPX ở tốc độ thấp) | **Cao** | Mở |
| S6 | ULPS: có dùng không, trình tự, TWAKEUP | Trung bình | Mở |
| S7 | Thời gian giữ LP-11 sau khi bật nguồn (TINIT phía Tx) | Trung bình | Mở |
| S8 | Chỉ CSI-2 v1.3, hay có tính năng v2.0 trở lên | Trung bình | Đã có từ HAS-CSI, nhờ xác nhận |
| S9 | Map lane và cực tính P/N trên board/package | Cao | Mở |
| S10 | Model mô phỏng của Tx | Cao | Mở |
| S11 | Chế độ test cho bring-up | Thấp | Mở |

---

## S1 — Dải tốc độ lane

**Câu hỏi.**
1. Mỗi sensor mode chạy ở tốc độ lane bao nhiêu? Tốc độ tối đa là bao nhiêu?
2. Có đổi tốc độ khi đang chạy không? Nếu có, đổi lúc nào, và mọi lane có đang ở LP lúc đó không?

**Đã biết từ HAS-CSI.** Giới hạn thiết kế là 1792 Mb/s/lane; OS04C10 chạy 750 Mb/s/lane. Chưa có
tốc độ của IMX274.

**Giả định hiện tại.** 80–1500 Mb/s ở bản R1, 80–1792 Mb/s ở bản R2. Chỉ đổi tốc độ khi mọi lane
đang ở LP.

## S2 — Số data lane

**Câu hỏi.** Mỗi sensor mode dùng 1, 2 hay 4 data lane? Có chế độ nào chạy ít lane hơn số lane được
nối trên board không?

**Đã biết từ HAS-CSI.** Rx hỗ trợ 1, 2 hoặc 4 data lane, cùng 1 clock lane.

**Giả định hiện tại.** Các lane không dùng giữ LP-11; Rx tắt chúng bằng `dl_enable_x`.

## S3 — Continuous hay non-continuous clock

**Câu hỏi.** Clock lane chạy continuous (luôn ở HS khi truyền) hay non-continuous (về LP giữa các
burst)? Có chuyển giữa hai chế độ khi đang chạy không?

**Đã biết từ HAS-CSI.** Hệ thống chỉ dùng continuous clock trong bản này.

**Giả định hiện tại.** Continuous clock. FSM của clock lane trong Rx xử lý được việc vào/ra LP giữa
các burst, nhưng đường dữ liệu thì chưa: delay line EoT chỉ xả khi `rxbyteclkhs` chạy, còn
non-continuous clock dừng TCLK-POST sau burst, sớm hơn lúc byte cuối ra PPI (HAS D-PHY §1.4, §4.6).
Nếu Tx cần non-continuous clock, nhờ báo sớm.

## S4 — Deskew

**Câu hỏi.**
1. Tx có gửi deskew burst không?
2. Nếu có: gửi lúc nào? Chỉ initial (sau power-up hoặc sau khi đổi tốc độ), hay cả periodic (ví dụ
   trong vertical blanking)?
3. Pattern và độ dài chính xác của deskew burst là gì?

**Vì sao cần.** Trên 1.5 Gb/s, deskew là bắt buộc. Rx phải nhận ra deskew burst để không coi nó là
dữ liệu, và ở bản R2 phải dùng nó để calibrate delay của từng lane. Chúng tôi không có spec D-PHY v1.2
gốc; pattern đang lấy từ nguồn thứ cấp.

**Giả định hiện tại.** Theo D-PHY v1.2 (nguồn thứ cấp):
- sync gồm 16 UI bit 1, tiếp theo là chuỗi `0101…`;
- burst initial dài ≥ 2^15 UI khi chạy trên 1.5 Gb/s.

Rx nhận ra deskew burst khi thấy ≥ 16 bit 1 sau HS-0.

## S5 — Bảng timing thực tế của Tx

**Câu hỏi.** Nhờ gửi giá trị thực tế (min/typ/max, theo từng tốc độ nếu có) và dải cấu hình được của:
- TLPX
- THS-PREPARE, **THS-ZERO**, **THS-TRAIL**, THS-EXIT
- TCLK-PREPARE, TCLK-ZERO, TCLK-PRE, TCLK-POST, TCLK-TRAIL

**Vì sao cần.**
- **THS-TRAIL max** quyết định độ sâu delay line EoT của Rx (`PARA_EOT_DELAY_BYTES`, mặc định
  32 byte). Delay line này dùng để cắt phần trailer ở cuối burst.
- **THS-ZERO max** liên quan tới cửa sổ tìm sync. D-PHY chỉ cho giá trị min của THS-PREPARE +
  THS-ZERO (≥ 145 ns + 10·UI), không cho max. Rx đã đếm cửa sổ từ word khác 0 đầu tiên, nên chịu được
  HS-0 dài. Dù vậy, cần giá trị thực để đặt test case.
- **THS-EXIT + TLPX ở tốc độ thấp.** Sau mỗi burst, Rx đợi cắt trailer xong mới về Stop. Vì vậy dưới
  khoảng 240 Mb/s, Rx chỉ nhận được burst kế tiếp khi THS-EXIT + TLPX lớn hơn khoảng 32·UI + 15 ns
  (415 ns ở 80 Mb/s; mức tối thiểu của spec là 100 ns + 50 ns). Nếu Tx gửi hai burst sát nhau ở tốc
  độ thấp với THS-EXIT và TLPX tối thiểu, nhờ báo lại.
- Các giá trị còn lại dùng để đặt các góc timing trong môi trường verify.

**Giả định hiện tại.** Đúng min/max của D-PHY v1.1 Table 14. Ngoại lệ đã biết: ràng buộc THS-EXIT +
TLPX ở trên, khi chạy dưới khoảng 240 Mb/s (HAS D-PHY §4.5).

## S6 — ULPS

**Câu hỏi.** Tx có dùng Ultra-Low Power State (ULPS) trên data lane và clock lane không? Trình tự
vào/ra ULPS thế nào? Tx giữ Mark-1 bao lâu khi thoát ULPS (TWAKEUP)?

**Giả định hiện tại.** Có dùng ULPS, với TWAKEUP ≥ 1 ms. Rx không cần timer riêng cho TWAKEUP: nó
thoát ULPS khi thấy Mark-1 rồi Stop.

## S7 — Thời gian giữ LP-11 sau khi bật nguồn

**Câu hỏi.** Sau khi bật nguồn hoặc reset, Tx giữ LP-11 trên mọi lane bao lâu trước khi truyền
(TINIT phía master)?

**Vì sao cần.** Rx chỉ coi lane đã khởi tạo xong khi thấy LP-11 liên tục ≥ TINIT phía slave
(100 µs). Nếu Tx giữ ngắn hơn, Rx sẽ báo `init_done` muộn, hoặc bỏ mất burst đầu tiên.

**Giả định hiện tại.** ≥ 1 ms (ví dụ trong D-PHY §6.11).

## S8 — Phiên bản CSI-2

**Câu hỏi.** Tx cố định theo CSI-2 v1.3, hay có dự định dùng tính năng của v2.0 trở lên (ví dụ LRTE,
EPD, scrambling)?

**Đã biết từ HAS-CSI.** Controller lấy CSI-2 v1.3 làm nền.

**Giả định hiện tại.** Chỉ CSI-2 v1.3.

## S9 — Map lane và cực tính P/N

**Câu hỏi.**
1. Trên board và package, lane logic của Tx nối tới lane vật lý nào của Rx? Có lane nào bị đảo P/N
   không?
2. Clock lane có bị đảo P/N không?

**Vì sao cần.** Rx đảo được cực P/N và map lại data lane bằng cấu hình, cho cả đường HS lẫn đường LP.
Đảo P/N còn làm đổi chỗ LP-01 và LP-10, nên phải biết trước để đặt cấu hình đúng. Bản nháp v0.6 không
đảo và không map clock lane (HAS D-PHY §4.3). Nếu clock lane bị đảo trên board, Rx sẽ hiểu yêu cầu HS
(LP-01) thành yêu cầu ULPS (LP-10).

**Giả định hiện tại.** Nối thẳng, không đảo, kể cả clock lane.

## S10 — Model mô phỏng của Tx

**Câu hỏi.**
1. Phía Tx cung cấp model mô phỏng dạng nào: analog/AMS, hay digital ở mức pad (LP dp/dn + chuỗi bit
   HS)?
2. Model mẫu mà chúng tôi đang có (`ref/mipi_tx_dphy_model`) lệch D-PHY ở ba điểm:
   - trail không phải bit cuối bị đảo;
   - THS-EXIT chỉ 50 ns trong một số trường hợp;
   - clock thẳng cạnh với data, thay vì lệch 90°.

   Tx thật của các bạn có theo đúng spec ở ba điểm này không?

**Vì sao cần.** Rx được verify bằng một Tx BFM viết theo đúng spec. Nếu có model thật của Tx, chúng
tôi sẽ chạy thêm model đó để bắt các khác biệt ngoài đời thật.

**Giả định hiện tại.** Tx thật theo đúng spec; chưa có model của Tx.

## S11 — Chế độ test cho bring-up

**Câu hỏi.** Tx có chế độ test (PRBS, pattern cố định) để dùng khi bring-up không?

**Giả định hiện tại.** Không giả định có.

---

## Trả lời

| ID | Trả lời | Người trả lời | Ngày |
|---|---|---|---|
| S1 | | | |
| S2 | | | |
| S3 | | | |
| S4 | | | |
| S5 | | | |
| S6 | | | |
| S7 | | | |
| S8 | | | |
| S9 | | | |
| S10 | | | |
| S11 | | | |
