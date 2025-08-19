import mimetypes
from requests import Session, Response
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
    def __init__(self, file_paths: list[Path]):
        self.file_paths: list[Path] = []

        if not isinstance(file_paths, list):
            print_log("Error", "file_paths 必须是一个列表。", "file_upload.uploadFile.__init__")
            raise TypeError

        for file_path in file_paths:
            if not isinstance(file_path, Path):
                print_log("Error", "列表中的每个元素必须是 pathlib.Path 类型的对象。", "file_upload.uploadFile.__init__")
                raise TypeError

        self.file_paths.extend(self.swap_to_upload_files(file_paths))

    def swap_to_upload_files(self, file_paths: list[Path]) -> list[Path]:
        """检查并清洗非法的上传文件

        Parameters
        ----------
        file_paths : list[Path]
            _description_

        Returns
        -------
        list[Path]
            _description_
        """
        # 定义合法文件类型
        video_formats = ["avi", "flv", "m4v", "mkv", "mov", "mp4", "3gp", "3gpp", "mpg", "rm", "rmvb", "swf", "webm", "wmv"]
        audio_formats = ["mp3", "m4a", "wav", "wma"]
        image_formats = ["jpeg", "jpg", "png", "gif", "bmp", "heic", "webp"]
        document_formats = ["txt", "pdf", "csv", "xls", "xlsx", "doc", "ppt", "pptx", "docx", "odp", "ods", "odt", "rtf"]
        archive_formats = ["zip", "rar", "tar"]

        main_formats = video_formats + audio_formats + image_formats + document_formats + archive_formats
        other_formats = ["mat", "dwg", "m", "mlapp", "slx", "mlx"]

        # 定义合法大小，主要格式3GB，其他格式2GB
        legal_file_max_size = (3*1024**3, 2*1024**3)

        swapped_to_upload_files = []

        for file_path in file_paths:
            file_size = file_path.stat().st_size
            if file_size == 0:
                print_log("Warning", f"{file_path.name} 为空！", "file_upload.uploadFile.swap_to_upload_files")
                continue

            file_type = file_path.suffix.replace('.', '')

            if file_type in main_formats:
                if file_size > legal_file_max_size[0]:
                    print_log("Warning", f"{file_path.name} 大小超出上限3GB！", "file_upload.uploadFile.swap_to_upload_files")
                    continue

                swapped_to_upload_files.append(file_path)
                continue
            
            if file_type in other_formats:
                if file_size > legal_file_max_size[1]:
                    print_log("Warning", f"{file_path.name} 大小超出上限2GB！", "file_upload.uploadFile.swap_to_upload_files")
                    continue

                swapped_to_upload_files.append(file_path)
                continue

            print_log("Warning", f"{file_path.name} 文件类型暂未支持上传。", "file_upload.uploadFile.swap_to_upload_files")
        
        return swapped_to_upload_files


    def upload(self, login_session: Session):
        """上传文件

        Parameters
        ----------
        login_session : Session
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

        upload_file_post_headers = {
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://courses.zju.edu.cn',
            'Referer': 'https://courses.zju.edu.cn/user/resources/files',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36'
        }

        for file_path in self.file_paths:
            file_name = self.get_file_name(file_path)
            file_size = self.get_file_size(file_path)
            file_mimetype = mimetypes.guess_type(file_path)

            # upload_data是更新文件用的表单，file_payload是put上传文件的表单
            upload_data['name'] = file_name
            upload_data['size'] = file_size
            file_payload = {
                'file': (file_name, file_path.read_bytes(), file_mimetype)
            }


            post_response = login_session.post(
                url="https://courses.zju.edu.cn/api/uploads",
                json=upload_data,
                headers=upload_file_post_headers)


            if post_response.status_code != 201:
                print_log("Error", f"文件 {file_name} 更新请求失败！", "file_upload.uploadFile.upload")
                print_log("Debug", f"服务器错误详情: {post_response.text}", "file_upload.uploadFile.upload")
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
            
    def get_file_size(self, file_path: Path)->int:
        """获得文件字节大小

        Parameters
        ----------
        file_path : Path
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
        if not hasattr(file_path, 'stat'):
            print_log("Error", "file_path 必须是 pathlib.Path 类型的对象。", "file_upload.uploadFile.get_file_size")
            raise TypeError
        
        file_size = file_path.stat().st_size
        
        return file_size

    def get_file_name(self, file_path: Path)->str:
        """获得文件名

        Parameters
        ----------
        file_path : Path
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
        if not hasattr(file_path, 'name'):
            print_log("Error", "file_path 必须是 pathlib.Path 类型的对象。", "file_upload.uploadFile.get_file_size")
            raise TypeError
        
        file_name = file_path.name

        return file_name