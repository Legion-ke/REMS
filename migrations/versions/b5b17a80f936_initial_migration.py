"""Initial migration

Revision ID: b5b17a80f936
Revises: 
Create Date: 2024-11-27 03:23:41.365582

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b5b17a80f936'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('property', schema=None) as batch_op:
        batch_op.add_column(sa.Column('agent_id', sa.Integer(), nullable=False))
        batch_op.create_foreign_key('fk_property_agent', 'user', ['agent_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('property', schema=None) as batch_op:
        batch_op.drop_constraint('fk_property_agent', type_='foreignkey')
        batch_op.drop_column('agent_id')

    # ### end Alembic commands ###