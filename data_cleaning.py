import pandas as pd
from geopy.geocoders import ArcGIS
import re
import time

# 1. 严格读取数据
csv_filename = "raw_data.csv" 
df = pd.read_csv(csv_filename)

# 自动锁定 G 列 (第 7 列，索引为 6)
g_col_idx = 6
g_column_name = df.columns[g_col_idx]
print(f"【安全锁定】G 列（源地址列）表头为: '{g_column_name}'")

# 2. 初始化 ArcGIS 编码器
geolocator = ArcGIS()

def clean_county_single_row(address):
    """
    针对单行地址的安全解析函数。
    """
    if pd.isna(address):
        return ""
    
    address_str = str(address).strip()
    # 如果G列是空的，严格返回空字符串
    if not address_str or address_str.lower() in ["nan", "null", "none", "."]:
        return ""
        
    # 清理多余空格
    address_str = re.sub(r'\s+', ' ', address_str)
    
    # 拆分逗号
    parts = [p.strip() for p in address_str.split(',') if p.strip()]
    
    # 策略 A：本地三段式解析 (针对 "Newport, Lincoln, OR" 等)
    if len(parts) >= 3:
        possible_county = parts[1]
        clean_name = re.sub(r'(?i)\s*County\s*', '', possible_county).strip()
        if clean_name.lower() not in ["or", "oregon", "wa", "washington", "usa"]:
            return clean_name
            
    # 策略 B：在线 API 智能兜底 (针对 "Corvallis, OR" 2段式等)
    query = address_str
    if "usa" not in address_str.lower():
        if "washington" in address_str.lower() or "wa" in address_str.lower():
            query = f"{address_str}, USA"
        else:
            query = f"{address_str}, Oregon, USA"
            
    for attempt in range(2):
        try:
            location = geolocator.geocode(query, out_fields="Subregion,Match_addr")
            if location and 'attributes' in location.raw:
                attrs = location.raw['attributes']
                county = attrs.get('Subregion', '')
                if county:
                    return county.replace(" County", "").strip()
                
                match_addr = attrs.get('Match_addr', '')
                if match_addr:
                    match = re.search(r",\s*([A-Za-z\s]+),\s*(Oregon|Washington)", match_addr, re.IGNORECASE)
                    if match:
                        found_county = match.group(1).strip()
                        if found_county.lower() not in address_str.lower():
                            return found_county.replace(" County", "").strip()
        except:
            if attempt < 1:
                time.sleep(1)
                continue
    
    return "Not Found"

# 3. 物理重构 DataFrame 的列结构（确保 AQ 列/第43列存在）
target_col_idx = 42  # AQ 列的索引是 42

# 如果当前的列数不够 43 列，我们安全地把列扩充到 43 列
if df.shape[1] < 43:
    print(f"当前表格只有 {df.shape[1]} 列，正在安全补齐至 43 列（AQ列）...")
    for i in range(df.shape[1], 43):
        col_name = f"Placeholder_Col_{i}"
        df[col_name] = ""

# 确保第 43 列的列名严格叫 'County_Clean'
cols = list(df.columns)
cols[target_col_idx] = 'County_Clean'
df.columns = cols

# 【核心修复】：强制将第 43 列的数据类型转为字符型 (object)，防止 float64 报错限制写入字符串
df['County_Clean'] = df['County_Clean'].astype(object)

print("【结构安全锁已激活】开始逐行对齐解析...")

# 4. 严格逐行（1对1）按索引位置填充，杜绝任何物理错位
start_time = time.time()
total_rows = len(df)

for idx in range(total_rows):
    # 1. 严格获取当前行 G 列的值
    g_val = df.iloc[idx, g_col_idx]
    
    # 2. 如果 G 列为空，AQ 列绝对不填任何东西
    if pd.isna(g_val) or str(g_val).strip().lower() in ["", "nan", "null"]:
        df.iloc[idx, target_col_idx] = ""
        continue
        
    # 3. 如果 G 列有值，进行解析
    parsed_county = clean_county_single_row(g_val)
    
    # 4. 严格写入当前行的 AQ 列（索引 42），绝不偏移
    df.iloc[idx, target_col_idx] = parsed_county
    
    # 打印进度
    if (idx + 1) % 50 == 0 or (idx + 1) == total_rows:
        print(f"进度: {idx + 1}/{total_rows} 行已完成对齐写入...")

# 5. 导出并保存
output_filename = "cleaned_data_aq_perfect.csv"
df.to_csv(output_filename, index=False)

print(f"\n🎉 绝对对齐清洗完成！耗时: {time.time() - start_time:.2f} 秒。")
print(f"请使用 Excel/Google Sheets 打开新生成的: {output_filename}")