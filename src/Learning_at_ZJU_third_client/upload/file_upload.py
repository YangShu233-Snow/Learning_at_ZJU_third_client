import mimetypes
from requests import Response
from requests.exceptions import HTTPError
from printlog.print_log import print_log
from pathlib import Path
from load_config import load_config, parse_config

QUERIES = {
    'data': ['resources_submission', 'apis_config', 'upload', 'data']
}

class uploadFile:
    """管理所有待上传的文件

    一般传入一个包含所有文件Path对象的列表，然后使用upload方法，自动构建所需的上传表单并上传文件。
    """    
    def __init__(self, *file_objects: Path):
        self.file_objects: list[Path] = []
        
        for file_object in file_objects:
            # 检查传入对象是否为 pathlib.Path 类型
            if not isinstance(file_object, Path):
                print_log("Error", "file_objects 必须是 pathlib.Path 类型的对象。", "file_upload.uploadFile.__init__")
                raise TypeError
            
            self.file_objects.append(file_object)

    def upload(self, login_session: Response):
        """上传文件

        Parameters
        ----------
        login_session : Response
            已经登录好的Session
        
        Return
        ------
        files_id : dict
            返回一个{文件名: 文件id}的字典

        Raises
        ------
        HTTPError
            当文件上传失败的时候，会抛出HTTPError
        """        
        files_id = {}
        api_list_config = load_config.apiListConfig().load_config()
        api_list_config_parser = parse_config.APIListConfigParser(api_list_config=api_list_config, queries=QUERIES)
        api_list_config_parser.get_config_data()
        upload_data_list = api_list_config_parser.unpack_result()
        # 返回的还是列表，需要提取一下
        upload_data = upload_data_list[0]

        for file_object in self.file_objects:
            file_name = self.get_file_name(file_object)
            file_size = self.get_file_size(file_object)
            file_mimetype = mimetypes.guess_type(file_object)

            # upload_data是更新文件用的表单，file_payload是put上传文件的表单
            upload_data['name'] = file_name
            upload_data['size'] = file_size
            file_payload = {
                'file': (file_name, file_object.read_bytes(), file_mimetype)
            }

            post_response: Response = login_session.post(url="https://courses.zju.edu.cn/api/uploads",json=upload_data)

            if post_response.status_code != 201:
                print_log("Error", f"文件 {file_name} 更新请求失败！", "file_upload.uploadFile.upload")
                raise HTTPError
            
            print_log("Info", f"文件 {file_name} 更新请求完成！", "file_upload.uploadFile.upload")

            put_url = post_response.json().get("upload_url")
            put_response: Response = login_session.put(url=put_url, files=file_payload)
            
            if put_response.status_code == 200:
                print_log("Info", f"文件 {file_name} 上传成功", "file_upload.uploadFile.upload")
            else:
                print_log("Error", f"文件 {file_name} 上传失败", "file_upload.uploadFile.upload")
                raise HTTPError
            
            file_id = post_response.json().get("id")
            files_id[file_name] = file_id

        return files_id
            
    def get_file_size(self, file_object: Path)->int:
        """获得文件字节大小

        Parameters
        ----------
        file_object : Path
            文件Path对象

        Returns
        -------
        int
            文件字节大小

        Raises
        ------
        TypeError
            当文件不是Path对象时候，报错TypeError
        """        
        if not hasattr(file_object, 'stat'):
            print_log("Error", "file_object 必须是 pathlib.Path 类型的对象。", "file_upload.uploadFile.get_file_size")
            raise TypeError
        
        file_size = file_object.stat().st_size
        
        return file_size

    def get_file_name(self, file_object: Path)->str:
        """获得文件名

        Parameters
        ----------
        file_object : Path
            文件对象Path

        Returns
        -------
        str
            文件名

        Raises
        ------
        TypeError
            当文件对象不是Path时候报错TypeError
        """        
        if not hasattr(file_object, 'name'):
            print_log("Error", "file_objectc 必须是 pathlib.Path 类型的对象。", "file_upload.uploadFile.get_file_size")
            raise TypeError
        
        file_name = file_object.name

        return file_name