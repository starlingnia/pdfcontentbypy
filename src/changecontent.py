import fitz  # PyMuPDF

def auto_fix_toc(input_pdf, output_pdf):
    doc = fitz.open(input_pdf)
    toc = []  
    
    # --- 阈值设置 ---
    # 建议先运行一次，看控制台打印的字号，再微调这里
    SIZE_H1 = 15.0  
    SIZE_H2 = 12.0

    print(f"正在分析 {input_pdf}...")

    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]
        
        # --- 状态变量 (用于合并多行标题) ---
        # pending_title: 暂存的标题文字
        # pending_level: 暂存的标题等级 (0=无, 1=一级, 2=二级)
        pending_title = []
        pending_level = 0
        
        def flush_title():
            """如果有暂存的标题，把它写入 TOC 列表，并清空暂存区"""
            nonlocal pending_title, pending_level
            if pending_title and pending_level > 0:
                # 把 ["Quantum", "Field..."] 拼接成 "Quantum Field..."
                full_title = " ".join(pending_title).strip()
                # 只有当标题不为空时才添加
                if full_title:
                    print(f"  [添加目录 L{pending_level}] P{page_num+1}: {full_title}")
                    toc.append([pending_level, full_title, page_num + 1])
            
            # 重置状态
            pending_title = []
            pending_level = 0

        # --- 遍历页面内容 ---
        for block in blocks:
            if "lines" not in block: continue
            
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    size = span["size"]
                    
                    if not text: continue
                    
                    # 1. 判断当前这行字的等级
                    current_level = 0
                    if size > SIZE_H1:
                        current_level = 1
                    elif size > SIZE_H2:
                        current_level = 2
                    
                    # 2. 核心合并逻辑
                    if current_level == 0:
                        # 如果遇到了正文(小字)，说明之前的标题结束了
                        flush_title()
                    else:
                        # 如果是标题字号
                        if current_level == pending_level:
                            # 等级一样（例如都是一级标题的两个部分），合并！
                            pending_title.append(text)
                        else:
                            # 等级不一样（例如从一级变成了二级，或者之前没标题），
                            # 先把旧的存了，开始记录新的
                            flush_title()
                            pending_level = current_level
                            pending_title.append(text)
        
        # 每一页结束时，强制保存一下手里剩下的标题
        flush_title()

    if not toc:
        print("未检测到目录，请检查 SIZE_H1 和 SIZE_H2 阈值是否设置过大。")
    else:
        print(f"共生成 {len(toc)} 条目录。")
        doc.set_toc(toc)
        doc.save(output_pdf)
        print(f"成功保存为: {output_pdf}")

# --- 运行 ---
input_file = "1000.pdf"  # 记得改这里
output_file = "book.pdf"
auto_fix_toc(input_file, output_file)