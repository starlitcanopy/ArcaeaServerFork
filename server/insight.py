from flask import Blueprint, request

from core.sql import Connect
from core.user import UserOnline
from core.error import ArcError

from .auth import auth_required
from .func import arc_try, success_return

bp = Blueprint('insight', __name__, url_prefix='/insight')

@bp.route('/me/complete/eden_append_1', methods=['POST'])
@auth_required(request)
@arc_try
def complete_eden(user_id):
    with Connect() as c:
        user = UserOnline(c, user_id)
        user.select_user()

        if user.insight_state == 1:
            raise ArcError('Cannot call this api.', 151, status=403)
        user.update_user_one_column("insight_state", 1)

        return success_return({
            "insight_state": user.insight_state
        })

@bp.route('/me/complete/lephon', methods=['POST'])
@auth_required(request)
@arc_try
def complete_lephon(user_id):
    with Connect() as c:
        user = UserOnline(c, user_id)
        user.select_user()

        if user.insight_state == 3 or user.insight_state == 4:
            raise ArcError('Cannot call this api.', 151, status=403)
        c.execute('''update user_world_map set lephon_nell_state = :y where user_id = :x''', {'x': user_id, 'y': 4})
        user.update_user_one_column("insight_state", 3)

        return success_return({
            "insight_state": user.insight_state
        })