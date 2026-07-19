## 5 Package: Core

### 5.1 Core::IdentifiedObject

## 5.1.1 Class: IdentifiedObject

基类

| 属性 | 类型 | 基数 |
|---|---|---|
| mRID | string | 1..1 |
| name | string | 0..1 |
| description | string | 0..1 |

## 5.1.2 Class: PowerSystemResource

PSR 基类

| 属性 | 类型 | 基数 |
|---|---|---|
| name | string | 0..1 |

| 继承 | 父类 |
|---|---|
| 父类 | IdentifiedObject |

## 5.1.3 Class: Measurement

测量值

| 属性 | 类型 | 基数 |
|---|---|---|
| measurementType | string | 1..1 |

| 关联端 | 目标类 | 基数 |
|---|---|---|
| PowerSystemResource | PowerSystemResource | 0..1 |

| 继承 | 父类 |
|---|---|
| 父类 | IdentifiedObject |

## 6 Package: Wires

### 6.1 Wires::Conductor

## 6.1.1 Class: Conductor

导线

| 属性 | 类型 | 基数 |
|---|---|---|
| length | float | 0..1 |
| ratedCurrent | float | 0..1 |

| 继承 | 父类 |
|---|---|
| 父类 | PowerSystemResource |

## 6.1.2 Class: ACLineSegment

交流线路段

| 属性 | 类型 | 基数 |
|---|---|---|
| r | float | 0..1 |
| x | float | 0..1 |

| 关联端 | 目标类 | 基数 |
|---|---|---|
| Conductor | Conductor | 1..1 |

| 继承 | 父类 |
|---|---|
| 父类 | Conductor |