"""fix job_id type

Revision ID: 1dc2a1b22b5a
Revises: 8844e0cfc7ff
Create Date: 2026-01-29 19:04:41.233484

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '1dc2a1b22b5a'
down_revision = '8844e0cfc7ff'
branch_labels = None
depends_on = None

def upgrade():
    # استخدام الاتصال المباشر لتنفيذ SQL مرن
    conn = op.get_bind()
    
    # حذف القيود فقط إذا كانت موجودة لتجنب الـ Crash
    conn.execute(sa.text('ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS agent_memory_job_id_fkey'))
    conn.execute(sa.text('ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS agent_memory_scholarship_id_fkey'))

    with op.batch_alter_table('agent_memory', schema=None) as batch_op:
        # تغيير نوع الأعمدة من Integer إلى String (Varchar)
        batch_op.alter_column('job_id',
               existing_type=sa.INTEGER(),
               type_=sa.String(length=500),
               existing_nullable=True)
        batch_op.alter_column('scholarship_id',
               existing_type=sa.INTEGER(),
               type_=sa.String(length=500),
               existing_nullable=True)
        
        # حذف عمود السكور القديم لو لسه موجود
        try:
            batch_op.drop_column('score_at_time')
        except:
            pass

def downgrade():
    with op.batch_alter_table('agent_memory', schema=None) as batch_op:
        batch_op.add_column(sa.Column('score_at_time', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.alter_column('scholarship_id',
               existing_type=sa.String(length=500),
               type_=sa.INTEGER(),
               existing_nullable=True)
        batch_op.alter_column('job_id',
               existing_type=sa.String(length=500),
               type_=sa.INTEGER(),
               existing_nullable=True)
