from base64 import b64encode
from os import urandom
from random import choices
from time import time

from .bgtask import BGTask, logdb_execute
from .config_manager import Config
from .constant import Constant
from .course import CoursePlay
from .error import NoData, StaminaNotEnough
from .item import ItemCore
from .song import Chart
from .sql import Connect, Query, Sql
from .util import get_today_timestamp, md5
from .world import BeyondWorldPlay, BreachedWorldPlay, WorldPlay


class Score:
    def __init__(self) -> None:
        self.c = None

        self.song: 'Chart' = Chart()
        self.score: int = None
        self.shiny_perfect_count: int = None
        self.perfect_count: int = None
        self.near_count: int = None
        self.miss_count: int = None
        self.health: int = None
        self.modifier: int = None
        self.time_played: int = None
        self.best_clear_type: int = None
        self.clear_type: int = None
        self.rating: float = None
        self.score_v2: float = None  # for `world_rank_score` of global rank

    def set_score(self, score: int, shiny_perfect_count: int, perfect_count: int, near_count: int, miss_count: int, health: int, modifier: int, time_played: int, clear_type: int):
        self.score = int(score) if score is not None else 0
        self.shiny_perfect_count = int(
            shiny_perfect_count) if shiny_perfect_count is not None else 0
        self.perfect_count = int(
            perfect_count) if perfect_count is not None else 0
        self.near_count = int(near_count) if near_count is not None else 0
        self.miss_count = int(miss_count) if miss_count is not None else 0
        self.health = int(health) if health is not None else 0
        self.modifier = int(modifier) if modifier is not None else 0
        self.time_played = int(time_played) if time_played is not None else 0
        self.clear_type = int(clear_type) if clear_type is not None else 0

    @staticmethod
    def get_song_grade(score: int) -> int:
        '''分数转换为评级'''
        if score >= 9900000:  # EX+
            return 6
        if score >= 9800000:  # EX
            return 5
        if score >= 9500000:  # AA
            return 4
        if score >= 9200000:  # A
            return 3
        if score >= 8900000:  # B
            return 2
        if score >= 8600000:  # C
            return 1
        return 0

    @property
    def song_grade(self) -> int:
        return self.get_song_grade(self.score)

    @staticmethod
    def get_song_state(clear_type: int) -> int:
        '''clear_type转换为成绩状态，用数字大小标识便于比较'''
        if clear_type == 3:  # PM
            return 5
        if clear_type == 2:  # FC
            return 4
        if clear_type == 5:  # Hard Clear
            return 3
        if clear_type == 1:  # Clear
            return 2
        if clear_type == 4:  # Easy Clear
            return 1
        return 0  # Track Lost

    @property
    def song_state(self) -> int:
        return self.get_song_state(self.clear_type)

    @property
    def all_note_count(self) -> int:
        return self.perfect_count + self.near_count + self.miss_count

    @property
    def is_valid(self) -> bool:
        '''分数有效性检查'''
        if self.shiny_perfect_count < 0 or self.perfect_count < 0 or self.near_count < 0 or self.miss_count < 0 or self.score < 0 or self.time_played <= 0:
            return False
        if self.song.difficulty not in (0, 1, 2, 3, 4):
            return False

        all_note = self.all_note_count
        if all_note == 0:
            return False

        calc_score = 10000000 / all_note * \
            (self.perfect_count + self.near_count/2) + self.shiny_perfect_count
        if abs(calc_score - self.score) >= 5:
            return False

        return True

    @staticmethod
    def calculate_rating(defnum: float, score: int) -> float:
        '''计算rating，谱面定数小于等于0视为Unrank，返回值会为-1，这里的defnum = Chart const'''
        if not defnum or defnum <= 0:
            # 谱面没定数或者定数小于等于0被视作Unrank
            return -1

        if score >= 10000000:
            ptt = defnum + 2
        elif score < 9800000:
            ptt = defnum + (score-9500000) / 300000
            ptt = max(ptt, 0)
        else:
            ptt = defnum + 1 + (score-9800000) / 200000

        return ptt

    @staticmethod
    def calculate_score_v2(defnum: float, shiny_perfect_count: int, perfect_count: int, near_count: int, miss_count: int) -> float:
        # 计算score_v2 refer: https://www.bilibili.com/video/BV1ys421u7BY
        # 谱面定数小于等于 0 视为 unranked，返回值会为 0
        if not defnum or defnum <= 0:
            return 0

        all_note = perfect_count + near_count + miss_count
        if all_note == 0:
            return 0
        shiny_ratio = shiny_perfect_count / all_note
        score_ratio = (perfect_count + near_count/2) / \
            all_note + shiny_perfect_count / 10000000
        acc_rating = max(0, min(shiny_ratio - 0.9, 0.095)) / 9.5 * 25
        score_rating = max(0, min(score_ratio - 0.99, 0.01)) * 75
        return defnum * (acc_rating + score_rating)

    def get_rating_by_calc(self) -> float:
        # 通过计算得到本成绩的 rating & score_v2
        if not self.song.defnum:
            self.song.c = self.c
            self.song.select()
        self.rating = self.calculate_rating(self.song.chart_const, self.score)
        self.score_v2 = self.calculate_score_v2(
            self.song.chart_const, self.shiny_perfect_count, self.perfect_count, self.near_count, self.miss_count)
        return self.rating

    def to_dict(self) -> dict:
        r = {
            "rating": self.rating,
            "modifier": self.modifier,
            "time_played": self.time_played,
            "health": self.health,
            "clear_type": self.clear_type,
            "miss_count": self.miss_count,
            "near_count": self.near_count,
            "perfect_count": self.perfect_count,
            "shiny_perfect_count": self.shiny_perfect_count,
            "score": self.score,
            "difficulty": self.song.difficulty,
            "song_id": self.song.song_id
        }
        if self.song.song_name is not None:
            r["song_name"] = self.song.song_name
        return r


class UserScore(Score):
    def __init__(self, c=None, user=None) -> None:
        '''
            parameter: `user` - `UserInfo`类或子类的实例
        '''
        super().__init__()
        self.c = c
        self.user = user
        self.rank = None  # 成绩排名，给Ranklist用的

    def select_score(self) -> None:
        '''查询成绩以及用户搭档信息，单次查询可用，不要集体循环查询'''
        self.c.execute('''select * from best_score where user_id = :a and song_id = :b and difficulty = :c''',
                       {'a': self.user.user_id, 'b': self.song.song_id, 'c': self.song.difficulty})
        x = self.c.fetchone()
        if x is None:
            raise NoData('No score data.')
        self.user.select_user_about_character()

        self.from_list(x)

    def from_list(self, x: list) -> 'UserScore':
        if self.song.song_id is None:
            self.song.song_id = x[1]
        if self.song.difficulty is None:
            self.song.difficulty = x[2]
        self.set_score(x[3], x[4], x[5], x[6], x[7], x[8], x[9], x[10], x[12])
        self.best_clear_type = int(x[11])
        self.rating = float(x[13])
        self.score_v2 = float(x[14])

        return self

    def to_dict(self, has_user_info: bool = True) -> dict:
        r = super().to_dict()
        r['best_clear_type'] = self.best_clear_type
        if has_user_info:
            r['user_id'] = self.user.user_id
            r['name'] = self.user.name
            r['is_skill_sealed'] = self.user.is_skill_sealed
            character = self.user.character_displayed
            r['is_char_uncapped'] = character.is_uncapped_displayed
            r['character'] = character.character_id
        if self.rank:
            r['rank'] = self.rank
        return r


class UserPlay(UserScore):
    def __init__(self, c=None, user=None) -> None:
        super().__init__(c, user)
        self.song_token: str = None
        self.song_hash: str = None
        self.submission_hash: str = None
        self.beyond_gauge: int = None
        self.unrank_flag: bool = None
        self.new_best_protect_flag: bool = None
        self.ptt: 'Potential' = None

        self.is_world_mode: bool = None
        self.stamina_multiply: int = None
        self.fragment_multiply: int = None
        self.prog_boost_multiply: int = None
        self.beyond_boost_gauge_usage: int = None

        self.ptt: Potential = None  # 临时用来计算用户ptt的
        self.world_play: 'WorldPlay' = None

        self.course_play_state: int = None
        self.course_play: 'CoursePlay' = None

        self.combo_interval_bonus: int = None  # 不能给 None 以外的默认值
        self.hp_interval_bonus: int = None  # 不能给 None 以外的默认值
        self.fever_bonus: int = None  # 不能给 None 以外的默认值
        self.skill_cytusii_flag: str = None
        self.skill_chinatsu_flag: str = None
        self.highest_health: int = None
        self.lowest_health: int = None

        self.invasion_flag: int = None  # 1: invasion_start, 2: invasion_hard
        self.nell_toggle: bool = False

    def to_dict(self) -> dict:
        # 不能super
        if self.is_world_mode is None or self.course_play_state is None:
            return {}
        if self.course_play_state == 4:
            r = self.course_play.to_dict()
        elif self.is_world_mode:
            r = self.world_play.to_dict()
        else:
            r = {}
        r['user_rating'] = self.user.rating_ptt
        r['finale_challenge_higher'] = self.rating > self.ptt.value
        r['global_rank'] = self.user.global_rank
        r['finale_play_value'] = 9.065 * self.rating ** 0.5  # by Lost-MSth
        return r

    @property
    def is_protected(self) -> bool:
        return self.health == -1 or int(self.score) >= 9800000 or self.new_best_protect_flag

    @property
    def is_valid(self) -> bool:
        '''分数有效性检查，带hash校验'''
        if not super().is_valid:
            return False

        # 歌曲谱面MD5检查，服务器没有谱面就不管了
        from .download import get_song_file_md5
        songfile_hash = get_song_file_md5(
            self.song.song_id, str(self.song.difficulty) + '.aff')
        if songfile_hash and songfile_hash != self.song_hash:
            return False

        x = f'''{self.song_token}{self.song_hash}{self.song.song_id}{self.song.difficulty}{self.score}{self.shiny_perfect_count}{
            self.perfect_count}{self.near_count}{self.miss_count}{self.health}{self.modifier}{self.clear_type}'''
        if self.combo_interval_bonus is not None:
            if self.combo_interval_bonus < 0 or self.combo_interval_bonus > self.all_note_count / 150:
                return False
            x = x + str(self.combo_interval_bonus)

        if self.hp_interval_bonus is not None and self.hp_interval_bonus < 0:
            return False

        if self.fever_bonus is not None and (self.fever_bonus < 0 or self.fever_bonus > self.perfect_count * 5):
            # fever 等级最高为 5
            return False

        y = f'{self.user.user_id}{self.song_hash}'
        checksum = md5(x+md5(y))

        if checksum != self.submission_hash:
            return False

        return True

    def get_play_state(self) -> None:
        '''检查token，当然这里不管有没有，是用来判断世界模式和课题模式的'''
        if self.song_token == '1145141919810':
            # 硬编码检查，绕过数据库
            self.is_world_mode = False
            self.course_play_state = -1
            return None

        self.c.execute(
            '''select * from songplay_token where token=:a ''', {'a': self.song_token})
        x = self.c.fetchone()
        if not x:
            self.is_world_mode = False
            self.course_play_state = -1
            return None
            # raise NoData('No token data.')
        # self.song.set_chart(x[2], x[3])
        if x[4]:
            self.course_play = CoursePlay(self.c, self.user, self)
            self.course_play.course_id = x[4]
            self.course_play.score = x[6]
            self.course_play.clear_type = x[7]
            self.is_world_mode = False
            self.course_play_state = x[5]
        else:
            self.stamina_multiply = int(x[8])
            self.fragment_multiply = int(x[9])
            self.prog_boost_multiply = int(x[10])
            self.beyond_boost_gauge_usage = int(x[11])
            self.skill_cytusii_flag = x[12]
            self.skill_chinatsu_flag = x[13]
            self.invasion_flag = x[14]
            self.is_world_mode = True
            self.course_play_state = -1

    def set_play_state_for_world(
        self,
        stamina_multiply: int = 1,
        fragment_multiply: int = 100,
        prog_boost_multiply: int = 0,
        beyond_boost_gauge_usage: int = 0,
        skill_cytusii_flag: str = None,
        skill_chinatsu_flag: str = None
    ) -> None:
        self.song_token = b64encode(urandom(64)).decode()
        self.stamina_multiply = int(stamina_multiply)
        self.fragment_multiply = int(fragment_multiply)
        self.prog_boost_multiply = int(prog_boost_multiply)
        self.beyond_boost_gauge_usage = int(beyond_boost_gauge_usage)
        self.skill_cytusii_flag = skill_cytusii_flag
        self.skill_chinatsu_flg = skill_chinatsu_flag
        if self.prog_boost_multiply != 0 or self.beyond_boost_gauge_usage != 0:
            self.c.execute('''select prog_boost, beyond_boost_gauge from user where user_id=:a''', {
                           'a': self.user.user_id})
            x = self.c.fetchone()
            if x:
                self.prog_boost_multiply = 300 if x[0] == 300 else 0
                if x[1] < self.beyond_boost_gauge_usage or self.beyond_boost_gauge_usage not in (100, 200):
                    # 注意：偷懒了，没判断是否是beyond图
                    self.beyond_boost_gauge_usage = 0

        self.clear_play_state()
        self.c.execute('''insert into songplay_token values(:t,:a,:b,:c,'',-1,0,0,:d,:e,:f,:g,:h,:i,:j)''', {
            'a': self.user.user_id, 'b': self.song.song_id, 'c': self.song.difficulty, 'd': self.stamina_multiply, 'e': self.fragment_multiply, 'f': self.prog_boost_multiply, 'g': self.beyond_boost_gauge_usage, 'h': self.skill_cytusii_flag, 'i': self.skill_chinatsu_flag, 'j': self.invasion_flag, 't': self.song_token})

        self.user.select_user_about_current_map()
        self.user.current_map.select_map_info()

        self.user.select_user_about_stamina()
        if self.user.stamina.stamina < self.user.current_map.stamina_cost * self.stamina_multiply:
            raise StaminaNotEnough('Stamina is not enough.')

        fatalis_stamina_multiply = 1
        self.user.select_user_about_character()
        if not self.user.is_skill_sealed:
            self.user.character.select_character_info()
            # invasion 扔骰子
            _flag = choices([0, 1, 2], [
                            max(1 - Constant.INVASION_START_WEIGHT - Constant.INVASION_HARD_WEIGHT, 0), Constant.INVASION_START_WEIGHT, Constant.INVASION_HARD_WEIGHT])[0]
            if self.user.is_insight_enabled and _flag != 0:
                self.invasion_flag = _flag
            elif self.user.character.skill_id_displayed == 'skill_fatalis':
                # 特殊判断hikari fatalis的双倍体力消耗
                fatalis_stamina_multiply = 2

        self.clear_play_state()
        self.c.execute('''insert into songplay_token values(:t,:a,:b,:c,'',-1,0,0,:d,:e,:f,:g,:h,:i,:j)''', {
            'a': self.user.user_id, 'b': self.song.song_id, 'c': self.song.difficulty, 'd': self.stamina_multiply, 'e': self.fragment_multiply, 'f': self.prog_boost_multiply, 'g': self.beyond_boost_gauge_usage, 'h': self.skill_cytusii_flag, 'i': self.skill_chinatsu_flag, 'j': self.invasion_flag, 't': self.song_token})

        self.user.stamina.stamina -= self.user.current_map.stamina_cost * \
            self.stamina_multiply * fatalis_stamina_multiply
        self.user.stamina.update()

    def set_play_state_for_course(self, use_course_skip_purchase: bool, course_id: str = None) -> None:
        '''课题模式打歌初始化'''
        self.song_token = 'c_' + b64encode(urandom(64)).decode()
        if course_id is not None:
            self.course_play.course_id = course_id

        self.course_play_state = 0
        self.course_play.score = 0
        self.course_play.clear_type = 3  # 设置为PM，即最大值

        self.c.execute('''insert into songplay_token values(?,?,?,?,?,?,?,?,1,100,0,0,"","",0)''', (self.song_token, self.user.user_id, self.song.song_id,
                                                                                                    self.song.difficulty, self.course_play.course_id, self.course_play_state, self.course_play.score, self.course_play.clear_type))
        self.user.select_user_about_stamina()
        if use_course_skip_purchase:
            x = ItemCore(self.c)
            x.item_id = 'core_course_skip_purchase'
            x.amount = -1
            x.user_claim_item(self.user)
        else:
            if self.user.stamina.stamina < Constant.COURSE_STAMINA_COST:
                raise StaminaNotEnough('Stamina is not enough.')
            self.user.stamina.stamina -= Constant.COURSE_STAMINA_COST
            self.user.stamina.update()

    def update_token_for_course(self) -> None:
        '''课题模式更新token，并查用户体力'''
        previous_token = self.song_token
        self.song_token = 'c_' + b64encode(urandom(64)).decode()
        self.c.execute('''update songplay_token set token=? where token=?''',
                       (self.song_token, previous_token))
        self.user.select_user_about_stamina()

    def update_play_state_for_course(self) -> None:
        self.c.execute('''update songplay_token set course_state=?, course_score=?, course_clear_type=? where token=?''',
                       (self.course_play_state, self.course_play.score, self.course_play.clear_type, self.song_token))

    def clear_play_state(self) -> None:
        self.c.execute('''delete from songplay_token where user_id=:a''', {
                       'a': self.user.user_id})

    def record_score(self) -> None:
        '''向log数据库记录分数，请注意列名不同'''
        logdb_execute('''insert into user_score values(?,?,?,?,?,?,?,?,?,?,?,?,?)''', (self.user.user_id, self.song.song_id, self.song.difficulty, self.time_played,
                                                                                       self.score, self.shiny_perfect_count, self.perfect_count, self.near_count, self.miss_count, self.health, self.modifier, self.clear_type, self.rating))

    def record_rating_ptt(self, user_rating_ptt: float) -> None:
        '''向log数据库记录用户ptt变化'''
        today_timestamp = get_today_timestamp()
        with Connect(Config.SQLITE_LOG_DATABASE_PATH) as c2:
            old_ptt = c2.execute('''select rating_ptt from user_rating where user_id=? and time=?''', (
                self.user.user_id, today_timestamp)).fetchone()

            old_ptt = 0 if old_ptt is None else old_ptt[0]
            if old_ptt != user_rating_ptt:
                c2.execute('''insert or replace into user_rating values(?,?,?)''',
                           (self.user.user_id, today_timestamp, user_rating_ptt))

    def upload_score(self) -> None:
        '''上传分数，包括user的recent更新，best更新，recent30更新，世界模式计算'''
        self.get_play_state()
        self.get_rating_by_calc()
        if self.rating < 0:
            self.unrank_flag = True
            self.rating = 0
        else:
            self.unrank_flag = False

        self.time_played = int(time())

        # 记录分数
        self.record_score()

        # recent更新
        self.c.execute('''update user set song_id = :b, difficulty = :c, score = :d, shiny_perfect_count = :e, perfect_count = :f, near_count = :g, miss_count = :h, health = :i, modifier = :j, clear_type = :k, rating = :l, time_played = :m  where user_id = :a''', {
            'a': self.user.user_id, 'b': self.song.song_id, 'c': self.song.difficulty, 'd': self.score, 'e': self.shiny_perfect_count, 'f': self.perfect_count, 'g': self.near_count, 'h': self.miss_count, 'i': self.health, 'j': self.modifier, 'k': self.clear_type, 'l': self.rating, 'm': self.time_played * 1000})

        # 成绩录入
        self.c.execute('''select score, best_clear_type from best_score where user_id = :a and song_id = :b and difficulty = :c''', {
            'a': self.user.user_id, 'b': self.song.song_id, 'c': self.song.difficulty})
        x = self.c.fetchone()
        if not x:
            self.new_best_protect_flag = True  # 初见保护
            self.c.execute('''insert into best_score values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                           (self.user.user_id, self.song.song_id, self.song.difficulty, self.score, self.shiny_perfect_count, self.perfect_count, self.near_count, self.miss_count,
                            self.health, self.modifier, self.time_played, self.clear_type, self.clear_type, self.rating, self.score_v2))
            self.user.update_global_rank()
        else:
            self.new_best_protect_flag = False
            if self.song_state > self.get_song_state(int(x[1])):  # best状态更新
                self.c.execute('''update best_score set best_clear_type = :a where user_id = :b and song_id = :c and difficulty = :d''', {
                    'a': self.clear_type, 'b': self.user.user_id, 'c': self.song.song_id, 'd': self.song.difficulty})
            if self.score >= int(x[0]):  # best成绩更新
                self.new_best_protect_flag = True
                self.c.execute('''update best_score set score = :d, shiny_perfect_count = :e, perfect_count = :f, near_count = :g, miss_count = :h, health = :i, modifier = :j, clear_type = :k, rating = :l, time_played = :m, score_v2 = :n  where user_id = :a and song_id = :b and difficulty = :c ''', {
                    'a': self.user.user_id, 'b': self.song.song_id, 'c': self.song.difficulty, 'd': self.score, 'e': self.shiny_perfect_count, 'f': self.perfect_count, 'g': self.near_count, 'h': self.miss_count, 'i': self.health, 'j': self.modifier, 'k': self.clear_type, 'l': self.rating, 'm': self.time_played, 'n': self.score_v2})
                self.user.update_global_rank()

        self.ptt = Potential(self.c, self.user)
        if not self.unrank_flag:
            self.ptt.r30_push_score(self)

        # 总PTT更新
        user_rating_ptt = self.ptt.value
        self.user.rating_ptt = int(user_rating_ptt * 100)
        BGTask(self.record_rating_ptt, user_rating_ptt)  # 记录总PTT变换
        self.c.execute('''update user set rating_ptt = :a where user_id = :b''', {
            'a': self.user.rating_ptt, 'b': self.user.user_id})

        # 世界模式判断
        if self.is_world_mode:
            self.user.select_user_about_world_play()
            self.user.current_map.select_map_info()
            if self.user.current_map.is_breached:
                self.world_play = BreachedWorldPlay(self.c, self.user, self)
            elif self.user.current_map.is_beyond:
                self.world_play = BeyondWorldPlay(self.c, self.user, self)
            else:
                self.world_play = WorldPlay(self.c, self.user, self)
            self.world_play.update()

        # 课题模式判断
        if self.course_play_state >= 0:
            self.course_play.update()


class Potential:
    '''
        用户潜力值计算处理类

        property: `user` - `User`类或子类的实例
    '''

    def __init__(self, c=None, user=None):
        self.c = c
        self.user = user

        self.r30_tuples: 'list[tuple[int, str, int, float]]' = None
        self.r30: 'list[Score]' = None

        self.b30: list = None

    @property
    def value(self) -> float:
        total = 0

        for kind, amount, weight in Constant.PTT_FORMULA:
            if kind == "recent":
                total += weight * self.recent_n(amount)
            elif kind == "best":
                total += weight * self.best_n(amount)

        return total

    def best_n(self, n) -> float:
        self.c.execute(f'''select rating from best_score where user_id = :a order by rating DESC limit {n}''', {
            'a': self.user.user_id})
        return sum(x[0] for x in self.c.fetchall())

    def select_recent_30_tuple(self) -> None:
        '''获取用户recent30数据'''
        self.c.execute(
            '''select r_index, song_id, difficulty, rating from recent30 where user_id = ? order by time_played DESC''', (self.user.user_id,))

        self.r30_tuples = [x for x in self.c.fetchall() if x[1] != '']

    def select_recent_30(self) -> None:
        self.c.execute(
            '''select song_id, difficulty, score, shiny_perfect_count, perfect_count, near_count, miss_count, health, modifier, time_played, clear_type, rating from recent30 where user_id = ? order by time_played DESC''', (self.user.user_id,))

        self.r30 = []
        for x in self.c.fetchall():
            if x[0] == '':
                continue
            s = Score()
            s.song.set_chart(x[0], x[1])
            s.set_score(*x[2:-1])
            s.rating = x[-1]
            self.r30.append(s)

    def recent_n(self, amount) -> float:
        '''获取用户recent10的总潜力值'''
        if self.r30_tuples is None:
            self.select_recent_30_tuple()

        max_dict = {}
        for x in self.r30_tuples:
            if (x[1], x[2]) not in max_dict or max_dict[(x[1], x[2])] < x[3]:
                max_dict[(x[1], x[2])] = x[3]

        top_n_rating = sorted(max_dict.values(), reverse=True)[:amount]
        return sum(top_n_rating)

    def recent_30_to_dict_list(self) -> list:
        if self.r30 is None:
            self.select_recent_30()

        return [x.to_dict() for x in self.r30]

    def update_one_r30(self, r_index: int, user_score: 'UserPlay | UserScore') -> None:
        '''更新数据表中的一条数据'''
        self.c.execute('''insert or replace into recent30 values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                       (self.user.user_id, r_index, user_score.time_played, user_score.song.song_id, user_score.song.difficulty,
                        user_score.score, user_score.shiny_perfect_count, user_score.perfect_count, user_score.near_count, user_score.miss_count, user_score.health, user_score.modifier, user_score.clear_type, user_score.rating))

        # 更新内存中的数据
        x = (r_index, user_score.song.song_id,
             user_score.song.difficulty, user_score.rating)
        if len(self.r30_tuples) < 30:
            self.r30_tuples.append(x)
            return

        for i in range(30):
            if self.r30_tuples[i][0] == r_index:
                self.r30_tuples[i] = x
                break

    def r30_push_score(self, user_score: 'UserPlay | UserScore') -> None:
        '''根据新成绩调整 r30'''
        if self.r30_tuples is None:
            self.select_recent_30_tuple()

        if len(self.r30_tuples) < 30:
            self.update_one_r30(len(self.r30_tuples), user_score)
            return None

        if user_score.is_protected:
            # 保护，替换最低的最旧的成绩
            f_tuples = list(
                filter(lambda x: x[-1] <= user_score.rating, self.r30_tuples))
            f_tuples.reverse()  # 从旧到新
            f_tuples = sorted(f_tuples, key=lambda x: x[-1])
            if not f_tuples:
                # 找不到更低的成绩，不更新
                return None

        unique_songs: 'dict[tuple[str, int], list[tuple[int, int, float]]]' = {}
        for i, x in enumerate(self.r30_tuples):
            unique_songs.setdefault((x[1], x[2]), []).append((i, x[0], x[3]))

        new_song = user_score.song.to_tuple()

        if len(unique_songs) >= 11 or (len(unique_songs) == 10 and new_song not in unique_songs):
            if user_score.is_protected:
                # 保护，替换最低的最旧的成绩
                self.update_one_r30(f_tuples[0][0], user_score)
            else:
                self.update_one_r30(self.r30_tuples[-1][0], user_score)
            return None

        filtered_songs = dict(filter(lambda x: len(
            x[1]) > 1, unique_songs.items()))  # 过滤掉只有单个成绩的

        if new_song in unique_songs and new_song not in filtered_songs:
            # 如果新成绩有相同谱面的唯一成绩在 r30 中，则它也应该有可能被替换
            filtered_songs[new_song] = unique_songs[new_song]

        if user_score.is_protected:
            # 保护，替换最低的最旧的成绩，此时需在 filtered_songs 中
            for x in f_tuples:
                if (x[1], x[2]) in filtered_songs:
                    self.update_one_r30(x[0], user_score)
                    return None
        else:
            # 找到符合条件的最旧成绩
            max_idx = -1
            max_r_index = -1
            for x in filtered_songs.values():
                for y in x:
                    if y[0] > max_idx:
                        max_idx = y[0]
                        max_r_index = y[1]

            self.update_one_r30(max_r_index, user_score)


class UserScoreList:
    '''
        用户分数查询类

        properties: `user` - `User`类或子类的实例
    '''

    def __init__(self, c=None, user=None):
        self.c = c
        self.user = user
        self.scores: list = None
        self.query: 'Query' = Query(['user_id', 'song_id', 'difficulty'], ['song_id'], [
                                    'rating', 'difficulty', 'song_id', 'score', 'time_played'])

    def to_dict_list(self) -> list:
        return [x.to_dict(has_user_info=False) for x in self.scores]

    def select_from_user(self, user=None) -> None:
        '''获取用户的best_score数据'''
        if user is not None:
            self.user = user

        self.query.query_append({'user_id': self.user.user_id})
        self.query.sort += [{'column': 'rating', 'order': 'DESC'}]
        x = Sql(self.c).select('best_score', query=self.query)

        self.scores = [UserScore(self.c, self.user).from_list(i) for i in x]

    def select_song_name(self) -> None:
        '''为所有成绩中的song_id查询song_name'''
        if self.scores is None:
            return
        for score in self.scores:
            self.c.execute(
                '''select name from chart where song_id = ?''', (score.song.song_id,))
            x = self.c.fetchone()
            score.song.song_name = x[0] if x else ''
