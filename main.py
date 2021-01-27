import os 
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.ml.feature import Word2Vec, Word2VecModel, BucketedRandomProjectionLSH, BucketedRandomProjectionLSHModel
import jieba

"""
说明：word2vec训练词向量，进而得到评论向量，然后LSH快速求评论向量近邻。

参考：
https://blog.csdn.net/weixin_43250857/article/details/107468470
https://blog.csdn.net/u013090676/article/details/82716911
https://spark.apache.org/docs/latest/api/python/pyspark.ml.html?highlight=word2vec#pyspark.ml.feature.Word2VecModel
"""

# 初始化jieba
jieba.initialize()

# spark会话（local[*]表示使用所有cpu）
spark = SparkSession.builder.master('local[*]').config("spark.driver.memory", "8g").appName('douban').getOrCreate()

# 加载豆瓣数据集
douban_df = spark.read.csv('./DMSC.csv', header=True)
"""
+---+--------------------+-------------+----------+------+----------------+----------+----+------------------------------------+----+
| ID|       Movie_Name_EN|Movie_Name_CN|Crawl_Date|Number|        Username|      Date|Star|                             Comment|Like|
+---+--------------------+-------------+----------+------+----------------+----------+----+------------------------------------+----+
|  0|Avengers Age of U...|  复仇者联盟2|2017-01-22|     1|            然潘|2015-05-13|   3|          连奥创都知道整容要去韩国。|2404|
|  1|Avengers Age of U...|  复仇者联盟2|2017-01-22|     2|      更深的白色|2015-04-24|   2| 非常失望，剧本完全敷衍了事，主线...|1231|
|  2|Avengers Age of U...|  复仇者联盟2|2017-01-22|     3|    有意识的贱民|2015-04-26|   2|     2015年度最失望作品。以为面面...|1052|
"""

# 对评论进行分词
def jieba_f(line):
    try:
        words = jieba.lcut(line, cut_all=False)
        return words
    except:
        return []
jieba_udf = udf(jieba_f, ArrayType(StringType()))
douban_df = douban_df.withColumn('Words', jieba_udf(col('Comment')))
"""
+---+--------------------+-------------+----------+------+----------------+----------+----+------------------------------------+----+----------------------------+
| ID|       Movie_Name_EN|Movie_Name_CN|Crawl_Date|Number|        Username|      Date|Star|                             Comment|Like|                       Words|
+---+--------------------+-------------+----------+------+----------------+----------+----+------------------------------------+----+----------------------------+
|  0|Avengers Age of U...|  复仇者联盟2|2017-01-22|     1|            然潘|2015-05-13|   3|          连奥创都知道整容要去韩国。|2404|  [ , 连, 奥创, 都, 知道,...|
|  1|Avengers Age of U...|  复仇者联盟2|2017-01-22|     2|      更深的白色|2015-04-24|   2| 非常失望，剧本完全敷衍了事，主线...|1231| [ , 非常, 失望, ，, 剧本...|
|  2|Avengers Age of U...|  复仇者联盟2|2017-01-22|     3|    有意识的贱民|2015-04-26|   2|     2015年度最失望作品。以为面面...|1052|     [ , 2015, 年度, 最, ...|
|  3|Avengers Age of U...|  复仇者联盟2|2017-01-22|     4|  不老的李大爷耶|2015-04-23|   4|   《铁人2》中勾引钢铁侠，《妇联1...|1045|    [ , 《, 铁人, 2, 》, ...|
"""

# word2vec训练词向量(输入：Words词序列，输出：embedding词嵌入向量)
word2vec = Word2Vec(vectorSize=20, numPartitions=4, maxIter=3, seed=33, inputCol='Words', outputCol='Embedding')
model_path = './word2vec_model'
try:
    word2vec_model = Word2VecModel.load(model_path)
except:
    word2vec_model = word2vec.fit(douban_df)
    word2vec_model.save(model_path)
"""
# 展示词向量
word2vec_model.getVectors().show(truncate=False)
+------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
|广义  |[0.2298308163881302,0.10184220224618912,0.11428806185722351,-0.2545117735862732,0.13371628522872925,0.38737785816192627,-0.18080611526966095,0.2912159264087677,-0.042845338582992554,0.007754012010991573,0.07340796291828156,0.21571871638298035,0.027845118194818497,-0.1927560269832611,-0.23800526559352875,-0.09630415588617325,0.26478031277656555,-0.02759205549955368,-0.035280026495456696,-0.11370658129453659]    |
|我愿用|[0.3569982349872589,-0.04008175805211067,-0.02228064462542534,-0.13809481263160706,0.11383146792650223,0.14169472455978394,0.01509785931557417,0.18307729065418243,-0.5875641107559204,0.03696838393807411,0.12065540999174118,0.0557398721575737,-0.2770899832248688,-0.4094037115573883,-0.2359398901462555,0.08770501613616943,0.1590811014175415,-0.4789951741695404,0.09150195866823196,0.2459736317396164]              |
|钟爱  |[0.16913776099681854,0.1437755525112152,-0.021099811419844627,0.27797627449035645,0.1678694784641266,0.5455443263053894,0.2237573117017746,0.6392733454704285,0.38522306084632874,-0.27834826707839966,-0.13266880810260773,-0.04945696145296097,0.007050633430480957,-0.15870216488838196,-0.21051383018493652,-0.1582833230495453,0.6880394220352173,-0.10668554157018661,-0.06236705929040909,-0.113636814057827]          |
|甩手  |[0.25139203667640686,0.055334556847810745,0.2298315018415451,-0.5309959053993225,-0.6890652179718018,0.40532222390174866,0.2501186728477478,-0.1895916908979416,-0.06725015491247177,0.5156218409538269,-0.3592650890350342,0.16960440576076508,-0.9050099849700928,-0.29024872183799744,0.011675757355988026,0.23859812319278717,0.31643491983413696,0.23006290197372437,0.2294362634420395,0.13764706254005432]          
"""

# 使用词embedding的平均得到评论embedding
douban_df = word2vec_model.transform(douban_df)
"""
+---+--------------------+-------------+----------+------+----------------+----------+----+------------------------------------+----+----------------------------+--------------------+
| ID|       Movie_Name_EN|Movie_Name_CN|Crawl_Date|Number|        Username|      Date|Star|                             Comment|Like|                       Words|           Embedding|
+---+--------------------+-------------+----------+------+----------------+----------+----+------------------------------------+----+----------------------------+--------------------+
|  0|Avengers Age of U...|  复仇者联盟2|2017-01-22|     1|            然潘|2015-05-13|   3|          连奥创都知道整容要去韩国。|2404|  [ , 连, 奥创, 都, 知道,...|[0.10938933864235...|
|  1|Avengers Age of U...|  复仇者联盟2|2017-01-22|     2|      更深的白色|2015-04-24|   2| 非常失望，剧本完全敷衍了事，主线...|1231| [ , 非常, 失望, ，, 剧本...|[0.10207881422985...|
|  2|Avengers Age of U...|  复仇者联盟2|2017-01-22|     3|    有意识的贱民|2015-04-26|   2|     2015年度最失望作品。以为面面...|1052|     [ , 2015, 年度, 最, ...|[0.04180616276784...|
"""

# 训练LSH实现评论embedding快速近邻向量检索
lsh = BucketedRandomProjectionLSH(inputCol='Embedding', outputCol='Buckets', numHashTables=3, bucketLength=0.1)
model_path = './lsh_model'
try:
    lsh_model = BucketedRandomProjectionLSHModel.load(model_path)
except:
    lsh_model = lsh.fit(douban_df)
    lsh_model.save(model_path)

# 评论向量embedding计算分桶
douban_df = lsh_model.transform(douban_df)
"""
+---+----------------------+-------------+----------+------+----------------+----------+----+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+----+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------------+
|ID |Movie_Name_EN         |Movie_Name_CN|Crawl_Date|Number|Username        |Date      |Star|Comment                                                                                                                                                                                                                                                                                  |Like|Words                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |Embedding                                                                                                                                                                                                                                                                                                                                                                                                                     |Buckets                 |
+---+----------------------+-------------+----------+------+----------------+----------+----+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+----+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+------------------------+
|0  |Avengers Age of Ultron|复仇者联盟2  |2017-01-22|1     |然潘            |2015-05-13|3   | 连奥创都知道整容要去韩国。                                                                                                                                                                                                                                                              |2404|[ , 连, 奥创, 都, 知道, 整容, 要, 去, 韩国, 。]                                                                                                                                                                                                                                                                                                                                                                                                                          |[0.10938933864235878,0.03443918861448765,-0.10702529400587082,-0.38637474924325943,0.15594946965575218,0.09199576601386071,0.031935117207467556,-0.09990134164690972,-0.20399864204227924,0.11699134185910226,-0.11464695297181607,-0.01393067641183734,0.477449905872345,0.06377089992165566,-0.0963845506310463,0.43218154385685925,0.12875955402851105,0.07581734843552113,0.09165327474474907,-0.4218080684542656]        |[[1.0], [-4.0], [-3.0]] |
|1  |Avengers Age of Ultron|复仇者联盟2  |2017-01-22|2     |更深的白色      |2015-04-24|2   | 非常失望，剧本完全敷衍了事，主线剧情没突破大家可以理解，可所有的人物都缺乏动机，正邪之间、妇联内部都没什么火花。团结-分裂-团结的三段式虽然老套但其实也可以利用积攒下来的形象魅力搞出意思，但剧本写得非常肤浅、平面。场面上调度混乱呆板，满屏的铁甲审美疲劳。只有笑点算得上差强人意。    |1231|[ , 非常, 失望, ，, 剧本, 完全, 敷衍了事, ，, 主线, 剧情, 没, 突破, 大家, 可以, 理解, ，, 可, 所有, 的, 人物, 都, 缺乏, 动机, ，, 正邪, 之间, 、, 妇联, 内部, 都, 没什么, 火花, 。, 团结, -, 分裂, -, 团结, 的, 三段式, 虽然, 老套, 但, 其实, 也, 可以, 利用, 积攒, 下来, 的, 形象, 魅力, 搞, 出, 意思, ，, 但, 剧本, 写得, 非常, 肤浅, 、, 平面, 。, 场面, 上, 调度, 混乱, 呆板, ，, 满屏, 的, 铁甲, 审美疲劳, 。, 只有, 笑, 点算, 得, 上, 差强人意, 。]                |[0.10207881422985982,0.009545592398087426,-0.005397121676118909,-0.27453956138001895,0.26000592432825304,0.20473303055254424,-0.030830345179022448,-0.07669864853889477,-0.039627203943559945,-0.030836417169378297,0.08670296354173887,-0.11762266961585095,0.3601643921262244,0.11058124398497479,-0.29385836420171874,0.2274733007908231,-0.11165728573062707,0.295819340103374,0.04263881457083654,-0.21918029104155012]  |[[1.0], [-4.0], [-3.0]] |
"""

# 求每个评论的embedding近邻（距离在一定阈值内的所有其他评论）
douban_df = lsh_model.approxSimilarityJoin(douban_df, douban_df, 0.1, 'Similarity')
douban_df.show(truncate=False)
"""

"""