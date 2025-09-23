from requests import Response
from requests import HTTPError

from ..printlog.print_log import print_log
from ..load_config import load_config, parse_config
from ..zjuAPI import zju_api

QUERIES = {
    'data': ['resources_submission', 'apis_config', 'submissions', 'data']
}

class submitAssignment:
    """管理所有需要提交到任务的数据，包含comment与附加的files
    """    
    def __init__(self, activity_id: int, comment: str, files_id: list[int]):
        self.activity_id = activity_id
        self.comment = comment
        self.files_id = files_id

    def submit(self, login_session: Response):
        # 加载模版表单，传入construct_post_data获得当前待提交任务的POST表单
        api_list_config = load_config.apiListConfig().load_config()
        parser = parse_config.APIListConfigParser(api_list_config, QUERIES)
        parser.get_config_data()
        parser_result = parser.unpack_result()
        
        for temple_data in parser_result:
            post_data = self.construct_post_data(temple_data)

        # 提交任务
        print(post_data)
        submissions = zju_api.submissionAPIFits(login_session=login_session, activity_id=self.activity_id, data=post_data)
        submit_responses = submissions.post_api_data()
        
        for submit_response in submit_responses:
            if submit_response.status_code != 201:
                print_log("Error", f"任务提交失败", "submit.submitAssignment.submit")
                print(submit_response.status_code)
                print(submit_response.json())
                raise HTTPError

        print_log("Info", f"任务提交成功", "submit.submitAssignment.submit")
        


    def construct_post_data(self, temple_data: dict)->dict:
        """构建POST请求表单

        Parameters
        ----------
        temple_data : dict
            提供的样板表单

        Returns
        -------
        dict
            返回构建好的请求表单
        """        
        post_data = temple_data

        # 修改comment内容和上传文件id
        post_data["comment"] = temple_data.get("comment", "").replace("{{{comment}}}", self.comment)
        post_data["uploads"].extend(self.files_id)

        return post_data