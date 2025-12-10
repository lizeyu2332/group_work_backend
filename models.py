from flask_sqlalchemy import SQLAlchemy

# 初始化数据库实例
db = SQLAlchemy()


class Contact(db.Model):
    __tablename__ = 'contacts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    is_bookmarked = db.Column(db.Boolean, default=False)  # 功能 1.1: 收藏

    # 关联关系：一个联系人对应多个联系方式
    # cascade='all, delete-orphan' 确保删除联系人时，其联系方式也被删除
    methods = db.relationship('ContactMethod', backref='contact', lazy=True, cascade="all, delete-orphan")


class ContactMethod(db.Model):
    __tablename__ = 'contact_methods'
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # 例如: 'phone', 'email', 'address'
    value = db.Column(db.String(200), nullable=False)  # 例如: '13812345678'
