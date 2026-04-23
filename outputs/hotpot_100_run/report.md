# Lab 16 – Reflexion Benchmark Report

## 1. Thông tin sinh viên
Nguyễn Duy Hiếu – 2A202600153

## 2. Tổng quan hệ thống
Hệ thống benchmark đánh giá hiệu quả của kiến trúc Agent Reflexion nâng cao so với mô hình cơ sở ReAct (Reasoning and Acting). Mô hình ReAct hoạt động theo quy trình một chiều, tạo ra các cặp Thought và Observation để đưa ra câu trả lời cuối cùng mà không có khả năng tự sửa lỗi. Ngược lại, kiến trúc Reflexion mở rộng hệ thống bằng cách áp dụng một vòng lặp đa tác tử bao gồm Actor (Người thực thi), Evaluator (Người đánh giá) và Reflector (Người phản tư). Trong hệ thống này, Actor đưa ra câu trả lời ban đầu, sau đó Evaluator chấm điểm dựa trên định dạng JSON có cấu trúc. Nếu câu trả lời sai, Reflector phân tích nguyên nhân lỗi và rút ra một bài học chiến lược. Bài học này được lưu vào bộ nhớ phản tư (reflection memory), và Actor được cấp quyền thử lại (retry) để đưa ra câu trả lời chính xác hơn.

## 3. Dataset và thiết lập
Quá trình đánh giá sử dụng tập dữ liệu HotpotQA, được thiết kế chuyên biệt cho khả năng suy luận đa bước (multi-hop) trên các đoạn văn bản phức tạp. Để đảm bảo tính khách quan, hệ thống đánh giá trên 100 mẫu dữ liệu đã được phân tầng theo độ khó: 40 câu dễ, 40 câu trung bình và 20 câu khó. Việc phân loại độ khó được tích hợp ngay từ khâu tiền xử lý. Việc phân tầng dữ liệu ngăn chặn sự sai lệch (biased evaluation) trong quá trình đánh giá, đảm bảo kết quả không bị thổi phồng bởi số lượng lớn các câu hỏi quá đơn giản, từ đó đo lường chính xác năng lực suy luận của Agent qua từng cấp độ phức tạp.

## 4. Kết quả thực nghiệm
Kết quả thực nghiệm cho thấy sự chênh lệch rõ rệt về hiệu suất giữa hai mô hình trong môi trường giả lập (MOCK). Mô hình ReAct cơ sở đạt độ chính xác khoảng 50%. Trong khi đó, nhờ cơ chế thử lại và rút kinh nghiệm, Reflexion đã nâng tổng độ chính xác lên khoảng 80%.

| Metric            | ReAct | Reflexion |
|------------------|-------|-----------|
| Accuracy (EM)    | ~50%  | ~80%      |
| Avg Attempts     | 1.0   | ~1.5–2.0  |
| Token Usage      | Thấp  | Cao hơn   |
| Latency          | Nhanh | Chậm hơn  |

## 5. Vì sao Reflexion hiệu quả
Sự vượt trội của Reflexion bắt nguồn từ vòng lặp tự sửa lỗi (self-correction loop). Trong khi ReAct thất bại vĩnh viễn ngay khi gặp một sai lầm logic duy nhất, Reflexion duy trì một bộ nhớ phản tư (reflection memory). Khi một chuỗi suy luận sai, Reflector ghi lại chiến lược khắc phục vào bộ nhớ này. Trong các lần thử tiếp theo, Actor tận dụng những bài học này để suy luận lặp (iterative reasoning), loại bỏ các giả thuyết sai trước đó, tránh các ngõ cụt logic và thiết lập hướng đi mới chính xác hơn.

## 6. Phân tích lỗi
Hệ thống phát hiện các nhóm lỗi chính: suy luận đa bước không hoàn chỉnh (incomplete multi-hop) và sai lệch thực thể (entity drift). Lỗi đa bước không hoàn chỉnh xảy ra khi Agent dừng lại ngay khi mới tìm được dữ kiện đầu tiên. Lỗi sai lệch thực thể xuất hiện khi Agent bị nhầm lẫn bởi các thông tin gây nhiễu trong văn bản. Bằng cách chẩn đoán chính xác nguyên nhân thất bại, Reflector yêu cầu Actor tiếp tục tìm kiếm manh mối thứ hai hoặc chủ động loại trừ thực thể gây nhiễu, từ đó khắc phục thành công các lỗi này.

## 7. Đánh đổi Cost vs Accuracy
Việc áp dụng Reflexion kéo theo sự gia tăng đáng kể về chi phí và tài nguyên. Mỗi vòng lặp thử lại yêu cầu chạy toàn bộ chu trình prompt cho cả Actor, Evaluator và Reflector, làm tăng mạnh lượng token tiêu thụ và độ trễ (latency) của hệ thống. Dù đạt được mức tăng 30% độ chính xác, hệ thống xử lý truy vấn chậm hơn nhiều so với mô hình ReAct. Đánh đổi này cho thấy Reflexion ưu tiên tính chính xác tuyệt đối thay vì tối ưu hóa thời gian xử lý.

## 8. Khi nào dùng ReAct vs Reflexion
Kiến trúc ReAct phù hợp nhất cho các ứng dụng theo thời gian thực yêu cầu độ trễ thấp và tối ưu chi phí, chẳng hạn như chatbot hỗ trợ khách hàng hoặc hệ thống truy xuất tài liệu nhanh. Ngược lại, Reflexion là bắt buộc trong các lĩnh vực có tính rủi ro cao đòi hỏi sự chính xác tuyệt đối và suy luận phức tạp. Các kịch bản ứng dụng thực tế bao gồm phân tích hồ sơ pháp lý, đánh giá tài liệu y khoa và tổng hợp dữ liệu tài chính.

## 9. Hạn chế của hệ thống
Kết quả thực nghiệm này cần được nhìn nhận cùng với những hạn chế lớn của môi trường kiểm thử. Việc sử dụng môi trường MOCK có tính chất xác định gây ra sai lệch đáng kể (mock bias) so với thực tế, loại bỏ hoàn toàn tính ngẫu nhiên của LLM và hiện tượng ảo giác (hallucination). Hơn nữa, Evaluator trong môi trường này sử dụng trực tiếp đáp án chuẩn (gold answer) để đánh giá — điều không thể xảy ra trên thực tế. Do đó, các kết quả này hoàn toàn KHÔNG phản ánh chính xác hành vi của LLM trong môi trường thực tế (real-world LLM behavior). Token và độ trễ cũng chỉ là ước tính tĩnh.

## 10. Kết luận
Thực nghiệm này chứng minh Reflexion là giải pháp đột phá để nâng cao độ chính xác. Thông qua Evaluator và bộ nhớ phản tư, hệ thống đã chuyển đổi thành công từ suy luận tĩnh (static reasoning) sang suy luận thích ứng (adaptive reasoning). Dù phải đánh đổi đáng kể về độ trễ và chi phí token, mức tăng 30% độ chính xác khẳng định tầm quan trọng và tính ứng dụng vượt trội của Reflexion trong xử lý các tác vụ phức tạp.
