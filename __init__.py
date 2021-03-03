"""Simple modulo para descargar archivos de internet"""
import warnings
try:
    from tqdm import tqdm, tqdm_gui
except ImportError:
    from contextlib import contextmanager

    @contextmanager
    def tqdm(iterable=None,*argv,**karg):
        print( '    ' if karg.get('nested',False) else '', karg.get('desc',''))
        yield iterable
    def wrapattr(file,*argv,**karg):
        return file
    tqdm.wrapattr = wrapattr
    tqdm_gui = tqdm
    alerta = "\nAlerta: tqdm no esta disponible, este modulo usa esa libreria como su barra de progreso.\n" \
          "Por favor instalarlo, Se puede hacer mediante: pip install tqdm\n" \
          "En windows se requiere ademas del modulo colorama para un correcto display\n\n"
    try:
        import colorama
        colorama.init(autoreset=True)
        warnings.warn(colorama.Fore.YELLOW + alerta + colorama.Fore.RESET)
        colorama.deinit()
        del colorama
    except ImportError:
        warnings.warn(alerta)

__all__=[ 'download', 'download_many', 'url_exist', 'getname' ]

import os, sys, time
from contextlib_recipes import closing, redirect_folder
from urllib.parse import unquote, urlparse, parse_qs
import requests
from valid_filenames import valid_file_name

if "win" in sys.platform:
    try:
        import colorama
        del colorama
    except ImportError:
        warnings.warn("Alerta: Este modulo requiere del modulo colorama para el correcto funcionamiento del modulo tqdm\n"\
              "Favor instalarlo mediante: pip install colorama\n\n")

#_path1 = os.path.expanduser("~/Downloads")
#_path2 = os.path.expanduser("~/Descargas")
#PATH   = os.path.normpath( next(filter(os.path.exists,(_path1,_path2)),os.getcwd()) )
PATH   = "."
PARTIALEXT = '.partialfile'
PARTIALEXT2 = '.partialstream'
_timeout=50


def url_exist(url:str,retries=5,espera=1,show=False) -> bool:
    """Determina si la url dada existe"""
    for _ in range(retries):
        try:
            with closing(requests.head(url, allow_redirects=True)) as r:
                if show:
                    print(r)
                return r.ok
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            time.sleep(espera)
    return False

def getname(url:str) -> str:
    """Regresa el ultimo componente de la url unquote o el file component
       del query de la url si existe
           
       >>> getname("www.example.com/video/avenger/trailer%20infinity.mp4")
       'trailer infinity.mp4'
       >>>
       >>> getname("www.example.com/video/avenger?file=trailer%20infinity.mp4")
       'trailer infinity.mp4'
       >>>"""
    url = urlparse(url)
    if url.query:
        qs = parse_qs(url.query)
        if "file" in qs:
            return unquote(qs["file"][0])	
    return unquote(url.path.split("/")[-1])

def get_download_headers(url:str, *, retries=1000, espera=1, ignore_error=True, verify=True) -> dict:
    """
    """

    result = dict()
    for intento in range(1,retries+1):
        try:
            with closing( requests.head(url, allow_redirects=True, verify=verify) ) as con:
                result["nombre"]  = getname(con.url)
                result["total"]   = int(con.headers.get('content-length',0)) or None
                result["resumes"] = con.headers.get('Accept-Ranges',"").lower() == 'bytes'
            return result
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            if not ignore_error:
                raise
            print("\n\n",time.asctime(),"\nError de adquiriendo informacion de descarga en intento",'{i}/{t}'.format(i=intento,t=retries),'\n',exc)
            time.sleep(espera)
        pass
    return


def download(url:str, nombre:str=None, carpeta:str=PATH, desc:str=None, verbose=True,*,
             chunk_size=2**16, timeout=_timeout, retries=1000, espera=1, 
             ignore_error=True, verify=True, **tqdm_karg) -> str:
    """Descarga un archivo desde la url dada a un archivo del nombre dado en la carpeta espesificada
       Regresa el path del archivo resultado si es exitoso.
    """
    if not url:
        print("no url")
        return ""
    tqdm_bar = tqdm_gui if 'idlelib' in sys.modules else tqdm
    head = get_download_headers(url, retries=retries, espera=espera, ignore_error=ignore_error, verify=verify)
    if head:
        nombre = valid_file_name(nombre or head["nombre"] )
        result = os.path.join(carpeta,nombre)
        if os.path.exists(result):
            return result
        if desc is None:
            desc = "descargando {nombre!r}".format(nombre=nombre)
        total = head["total"]
        config = dict(allow_redirects = True,
                      verify          = verify,
                      stream          = True,
                      timeout         = timeout,
                      )
        tqdm_karg.update( unit         = "B",
                          unit_scale   = True,
                          leave        = False,
                          miniters     = 1,
                          desc         = desc,
                          total        = total,
                          unit_divisor = 1024,
                         )
        if head["resumes"]:
            data = os.path.join(carpeta,nombre+PARTIALEXT)
        else:
            assert not os.path.exists( os.path.join(carpeta,nombre+PARTIALEXT) ), "partialfile file exist for no resumible download"
            data = os.path.join(carpeta,nombre+PARTIALEXT2)
            if verbose: print("\nEsta descarga no puede ser resumida\n")                         
        for intento in range(1,retries+1):
            try:
                resume_header = None
                current = 0
                if head["resumes"] and os.path.exists(data):
                    current = os.stat(data).st_size
                    if total is not None:
                        assert current <= total, "inconsistent file size"
                    resume_header = {'Range': 'bytes={current}-'.format(current=current) }
                tqdm_karg["initial"] = current
                config["headers"] = resume_header 
                with open(data, "ab" if current else "wb") as file, closing( requests.get(url,**config ) ) as con:
                    if verbose: print("\n\n",time.asctime(),"Inicio de descarga" if intento==1 else "Re-Inicio de descarga")
                    with tqdm_bar(**tqdm_karg) as progress_bar:
                        for chunk in con.iter_content(chunk_size):
                            file.write(chunk)
                            progress_bar.update(len(chunk))
                if total is not None:
                    assert total == os.stat(data).st_size, "incomplete download"
                os.rename(data,result)
                if verbose: print("\n\n",time.asctime(),"Descarga completa")
                return result
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.ChunkedEncodingError) as exc:
                if not ignore_error:
                    raise
                print("\n\n",time.asctime(),"\nError de descarga en intento",'{i}/{t}'.format(i=intento,t=retries),'\n',exc)
                time.sleep(espera)
            except AssertionError as e:
                print("\n\n",time.asctime(),e)
                raise
            pass
        print(time.asctime(),"Falla al decargar:",nombre,url)
    else:
        print(time.asctime(),"Falla adquiriendo informacion de descarga:",url)
    return ""




def download_many(archivos:[("url","nombre")], carpeta:str=PATH, verbose=False, *, 
                  ignore_error:bool=True, timeout=_timeout, retries=5, 
                  espera=1, _gui:bool=False, **tqdm_karg) -> list:
    """Descarga los archivos espesificados en la carpeta dada
       Regresa una lista con los archivos descargados exitosamente"""
    if _gui:
        progress_bar = tqdm_gui
    else:
        progress_bar = tqdm_gui if 'idlelib' in sys.modules else tqdm
    if not os.path.exists(carpeta):
        print("creando carpeta:",carpeta)
        os.mkdir(carpeta)
        print("listo",flush=True)
    with redirect_folder(carpeta):
        total_archivos   = list( archivos )
        total            = len(total_archivos)
        pendiente        = [ x for x in total_archivos if not os.path.exists(x[1]) ]
        listo            = total - len(pendiente)
        exitos           = []
    with progress_bar(pendiente, total=total, initial=listo, **tqdm_karg) as progreso:
        for url,name in progreso:
            try:
                result = download(url, name,
                                  carpeta  = carpeta,
                                  desc     = name,
                                  timeout  = timeout,
                                  retries  = retries,
                                  espera   = espera,
                                  verbose  = verbose,
                                  leave    = False,
                                  position = 1 + tqdm_karg.get("position",0),
                                 )
                if result:
                    exitos.append( (name,result) )
                else:
                    print("\n\nNo se pudo descargar:",url,"\n", name, flush=True)
            except requests.RequestException as error:
                print("\n\nError al descargar:",url,"\n",name,'\n',error, flush=True)
                if not ignore_error:
                    raise
    return exitos
