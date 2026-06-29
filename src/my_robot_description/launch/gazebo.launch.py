import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch.substitutions import Command
from launch_ros.parameter_descriptions import ParameterValue
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    pkg_path = get_package_share_directory('my_robot_description')

    xacro_path = os.path.join(pkg_path, 'urdf', 'mobile_robot.urdf.xacro')
    robot_description = ParameterValue(
        Command(['xacro ', xacro_path]),
        value_type=str
    )

    world_path = os.path.join(pkg_path, 'worlds', 'obstacle_world.world')
    mapper_params_path = os.path.join(pkg_path, 'config', 'mapper_params_online_async.yaml')
    rviz_config = os.path.join(pkg_path, 'rviz', 'default.rviz')

    # --- Gazebo ---
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(
                get_package_share_directory('gazebo_ros'),
                'launch', 'gazebo.launch.py'
            )
        ]),
        launch_arguments={'world': world_path}.items()
    )

    # --- Robot State Publisher ---
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': True
        }],
        output='screen'
    )

    # --- Spawn Robot ---
    # z=0.05 to avoid drop impact corrupting initial odometry
    spawn_robot = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        arguments=[
            '-topic', 'robot_description',
            '-entity', 'mobile_robot',
            '-x', '0', '-y', '0', '-z', '0.10'
        ],
        output='screen'
    )

    # --- Static Transforms for fixed joints ---
    # lidar_link and camera_link were publishing at timestamp 0.0
    # explicit static_transform_publisher fixes this
    static_tf_lidar = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_tf_lidar',
        arguments=['0.15', '0', '0.12', '0', '0', '0', 'base_link', 'lidar_link'],
        parameters=[{'use_sim_time': True}]
    )

    static_tf_camera = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_tf_camera',
        arguments=['0.20', '0', '0.14', '0', '0', '0', 'base_link', 'camera_link'],
        parameters=[{'use_sim_time': True}]
    )

    # --- Controllers ---
    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster'],
    )

    diff_drive_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['diff_drive_controller'],
    )

    # --- SLAM Toolbox ---
    slam_toolbox = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        parameters=[
            mapper_params_path,
            {'use_sim_time': True}
        ],
        output='screen'
    )

    # --- RViz ---
    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_config],
        parameters=[{'use_sim_time': True}],
        output='screen'
    )

    # --- Staggered startup to avoid race conditions ---
    # 3s: Gazebo fully loaded, activate controllers
    delayed_controllers = TimerAction(
        period=3.0,
        actions=[joint_state_broadcaster_spawner, diff_drive_spawner]
    )

    # 6s: controllers active, TF stable, SLAM can start cleanly
    delayed_slam = TimerAction(
        period=6.0,
        actions=[slam_toolbox]
    )

    # 8s: everything ready, RViz starts with no stale TF
    delayed_rviz = TimerAction(
        period=8.0,
        actions=[rviz]
    )

    return LaunchDescription([
        gazebo,
        robot_state_publisher,
        spawn_robot,
        static_tf_lidar,
        static_tf_camera,
        delayed_controllers,
        delayed_slam,
        delayed_rviz,
    ])
