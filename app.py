import os
import pandas as pd
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from models import db, Contact, ContactMethod

app = Flask(__name__)

# --- 配置 ---
# 使用本地 SQLite 数据库
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///address_book.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 允许跨域 (CORS)
CORS(app)

# 绑定数据库
db.init_app(app)

# 启动时自动创建表
with app.app_context():
    db.create_all()


# --- 辅助函数 ---
def format_contact(contact):
    """将数据库对象转换为 JSON 格式给前端"""
    methods = {}
    for method in contact.methods:
        if method.type not in methods:
            methods[method.type] = []
        methods[method.type].append(method.value)

    return {
        'id': contact.id,
        'name': contact.name,
        'is_bookmarked': contact.is_bookmarked,
        'methods': methods
    }


# --- API 路由 ---

# 1. 获取所有联系人 & 新增联系人
@app.route('/contacts', methods=['GET', 'POST'])
def handle_contacts():
    if request.method == 'GET':
        contacts = Contact.query.order_by(Contact.is_bookmarked.desc(), Contact.id.desc()).all()
        return jsonify([format_contact(c) for c in contacts])

    if request.method == 'POST':
        data = request.json
        if not data or 'name' not in data:
            return jsonify({'error': 'Name is required'}), 400

        new_contact = Contact(name=data['name'])
        db.session.add(new_contact)
        db.session.commit()

        methods = data.get('methods', [])
        for m in methods:
            if m.get('value'):
                db.session.add(ContactMethod(
                    contact_id=new_contact.id,
                    type=m['type'],
                    value=m['value']
                ))

        db.session.commit()
        return jsonify(format_contact(new_contact)), 201


# 2. 删除联系人
@app.route('/contacts/<int:id>', methods=['DELETE'])
def delete_contact(id):
    contact = Contact.query.get_or_404(id)
    db.session.delete(contact)
    db.session.commit()
    return jsonify({'message': 'Deleted successfully'}), 200


# 3. 切换收藏状态
@app.route('/contacts/<int:id>/bookmark', methods=['PUT'])
def toggle_bookmark(id):
    contact = Contact.query.get_or_404(id)
    contact.is_bookmarked = not contact.is_bookmarked
    db.session.commit()
    return jsonify(format_contact(contact))


# --- 4. 导出中文 Excel (修改部分) ---
@app.route('/export', methods=['GET'])
def export_excel():
    contacts = Contact.query.all()
    data_list = []

    for c in contacts:
        # 基础信息 (中文表头)
        row = {
            '姓名': c.name,
            '是否收藏': '是' if c.is_bookmarked else '否'
        }

        # 提取联系方式
        # 注意：数据库里存的 type 还是 'phone'/'email' (为了方便前端逻辑)
        # 但导出的 Excel 表头我们要变成中文
        phones = [m.value for m in c.methods if m.type == 'phone']
        emails = [m.value for m in c.methods if m.type == 'email']
        addresses = [m.value for m in c.methods if m.type == 'address']
        socials = [m.value for m in c.methods if m.type == 'social']

        # 多个值用逗号隔开
        row['手机'] = ', '.join(phones)
        row['邮箱'] = ', '.join(emails)
        row['地址'] = ', '.join(addresses)
        row['社交账号'] = ', '.join(socials)

        data_list.append(row)

    df = pd.DataFrame(data_list)
    # 定义列的顺序
    columns = ['姓名', '是否收藏', '手机', '邮箱', '地址', '社交账号']
    # 重新排序并保存 (防止没有数据的列不显示)
    # 使用 reindex 确保所有列都存在，fill_value 填充空值
    df = df.reindex(columns=columns, fill_value='')

    filename = 'contacts_export_cn.xlsx'
    df.to_excel(filename, index=False)

    return send_file(filename, as_attachment=True, download_name='address_book_cn.xlsx')


# --- 5. 导入中文 Excel (修改部分) ---
@app.route('/import', methods=['POST'])
def import_excel():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']

    try:
        df = pd.read_excel(file)
        df = df.fillna('')

        count = 0
        for _, row in df.iterrows():
            # 识别中文列名 '姓名'
            name = str(row.get('姓名', '')).strip()
            if not name: continue

            contact = Contact(name=name)
            # 识别中文 '是'
            bookmark_val = str(row.get('是否收藏', '')).strip()
            if bookmark_val == '是':
                contact.is_bookmarked = True

            db.session.add(contact)
            db.session.commit()

            # 映射表：中文列名 -> 数据库内部 type
            type_mapping = {
                '手机': 'phone',
                '邮箱': 'email',
                '地址': 'address',
                '社交账号': 'social'
            }

            for cn_header, db_type in type_mapping.items():
                if cn_header in row and row[cn_header]:
                    values = str(row[cn_header]).split(',')
                    for v in values:
                        if v.strip():
                            db.session.add(ContactMethod(
                                contact_id=contact.id,
                                type=db_type,
                                value=v.strip()
                            ))
            count += 1

        db.session.commit()
        return jsonify({'message': f'成功导入 {count} 位联系人'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # 端口保持 5001
    app.run(debug=True, port=5001)
